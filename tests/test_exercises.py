from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import embeddings
from backend.app.agents import copilot
from backend.app.db import SessionLocal
from backend.app.exercises import CRISIS_LINE, NOTICE
from backend.app.main import app
from backend.app.models import (Alert, Assignment, Checkin, IntakeResponse, KbChunk, KbDocument, PendingAction,
                                User)
from backend.app.rag import Retrieved
from backend.app.risk_data import HARD_NEGATIVES_15
from backend.app.safety import (CRISIS_MESSAGE, clinical_output_violations, evaluate_classifier, risk_check,
                                risk_scan)
from test_copilot import FakeModel, _h, _setup_case, world  # noqa: F401  (world is a fixture)

RISK_30 = [  # synthetic, held out from the classifier's training phrases
    "I want to end it all", "some days I wish I was dead", "I have thoughts of not wanting to be here",
    "I am thinking of taking my own life", "I feel I should just kill myself", "I want to hurt myself tonight",
    "I don't want to live like this", "the world is better off without me", "I have been cutting myself",
    "I can't go on any more",
    "मैं जीना नहीं चाहता", "मुझे अब मर जाना चाहिए, मैं मरना चाहती हूँ", "मैं आत्महत्या करने की सोच रहा हूँ",
    "मुझे जीने की इच्छा नहीं है", "मैं अपनी जान दे दूँगा", "मुझे खुद को नुकसान पहुँचाने का मन है",
    "main marna chahti hoon", "mujhe jeene ka mann nahi hai", "main khudkushi kar loonga", "meri jaan dene ka mann hai",
    "ನನಗೆ ಸಾಯಬೇಕು ಅನಿಸುತ್ತದೆ", "ನಾನು ಆತ್ಮಹತ್ಯೆ ಮಾಡಿಕೊಳ್ಳಬೇಕು", "ನನಗೆ ಬದುಕಲು ಇಷ್ಟವಿಲ್ಲ",
    "ನನ್ನ ಜೀವನ ಸಾಕು ಅನಿಸಿದೆ", "ನಾನು ಸಾಯುವ ಮನಸ್ಸು ಮಾಡಿದ್ದೇನೆ", "naanu saayabeku anisuttide",
    "nanage aatmahatye maadkollabeku", "badukalu ishta illa nanage", "nanage jeevana saaku", "nanage saayabekagide",
]
HARD_NEGATIVES = [
    "this deadline is killing me", "I am dying to see the new film", "I killed it at work today",
    "मुझे रात को नींद नहीं आती", "mujhe kaam ka bahut tension hai", "ನನಗೆ ರಾತ್ರಿ ನಿದ್ರೆ ಬರುವುದಿಲ್ಲ",
]


@pytest.fixture
def real_chunk(world):
    """A KB chunk for the 'thought-record' document so release candidates map to a library exercise."""
    from backend.app.embeddings import get_embedder
    created = None
    with SessionLocal() as db:
        doc = db.scalar(select(KbDocument).where(KbDocument.slug == "thought-record"))
        if doc is None:
            doc = created = KbDocument(slug="thought-record", title="Thought record", approach="CBT", language="en",
                                       source_inspired_by="test", body="thought record steps", content_hash="x")
            db.add(doc)
            db.flush()
        chunk = db.scalar(select(KbChunk).where(KbChunk.document_id == doc.id))
        if chunk is None:
            chunk = KbChunk(document_id=doc.id, text="thought record steps", approach="CBT", language="en",
                            topic_tags=["thought-record"], embedding=get_embedder().embed_passages(["thought record steps"])[0])
            db.add(chunk)
        db.commit()
        chunk_id, doc_id = chunk.id, doc.id
    yield chunk_id
    if created is not None:
        with SessionLocal() as db:
            db.query(KbChunk).filter(KbChunk.document_id == doc_id).delete()
            db.query(KbDocument).filter(KbDocument.id == doc_id).delete()
            db.commit()


def _briefing(chunk_id: int) -> dict:
    return {"summary": "The notes point toward exam worry, please confirm.",
            "suggestions": [{"text": "Consider a thought record for the exam thoughts.", "chunk_ids": [chunk_id],
                             "note_quotes": ["I lie awake most nights"]}]}


def _draft_release(client, w, monkeypatch, chunk_id: int) -> dict:
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "retrieve_knowledge",
                        lambda db, q, a: [Retrieved(id=chunk_id, text="t", similarity=0.9, rrf_score=0.03, title="Thought record")])
    monkeypatch.setattr(copilot, "call_model", FakeModel([_briefing(chunk_id)]))
    client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"]))
    items = client.get("/therapists/me/pending-actions", headers=_h(w["ta"])).json()["items"]
    return next(i for i in items if i["type"] == "release_exercise")


def _approved_assignment(client, w, monkeypatch, chunk_id: int) -> int:
    action = _draft_release(client, w, monkeypatch, chunk_id)
    r = client.post(f"/pending-actions/{action['id']}/approve",
                    headers=_h(w["ta"]) | {"Idempotency-Key": action["idempotency_key"]})
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text
    return client.get("/client/assignments", headers=_h(w["ca"])).json()["items"][0]["assignment_id"]


def _forbid_model(monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("model client must not be called")
    monkeypatch.setattr(copilot, "call_model", boom)
    monkeypatch.setattr(httpx, "post", boom)


# ---------- release flow ----------

def test_release_only_after_approval_and_only_once(world, real_chunk, monkeypatch) -> None:
    client, w = world
    action = _draft_release(client, w, monkeypatch, real_chunk)
    assert action["status"] == "pending" and action["payload"]["exercise"] == "thought_record"
    # nothing reaches the client before approval
    assert client.get("/client/assignments", headers=_h(w["ca"])).json()["items"] == []
    assert client.get("/client/dashboard", headers=_h(w["ca"])).json()["approved_exercises"] == []
    url, key = f"/pending-actions/{action['id']}/approve", action["idempotency_key"]
    assert client.post(url, headers=_h(w["ta"])).status_code == 409  # key required
    assert client.post(url, headers=_h(w["ta"]) | {"Idempotency-Key": "wrong"}).status_code == 409
    for _ in range(3):
        assert client.post(url, headers=_h(w["ta"]) | {"Idempotency-Key": key}).json()["status"] == "approved"
    with SessionLocal() as db:
        assert db.query(Assignment).filter(Assignment.pending_action_id == action["id"]).count() == 1
    mine = client.get("/client/assignments", headers=_h(w["ca"])).json()
    assert [i["exercise"] for i in mine["items"]] == ["thought_record"]
    assert client.get("/client/dashboard", headers=_h(w["ca"])).json()["approved_exercises"][0]["exercise"] == "thought_record"


def test_rejected_release_creates_no_assignment(world, real_chunk, monkeypatch) -> None:
    client, w = world
    action = _draft_release(client, w, monkeypatch, real_chunk)
    r = client.post(f"/pending-actions/{action['id']}/reject", headers=_h(w["ta"]) | {"Idempotency-Key": action["idempotency_key"]})
    assert r.json()["status"] == "rejected"
    assert client.post(f"/pending-actions/{action['id']}/approve",
                       headers=_h(w["ta"]) | {"Idempotency-Key": action["idempotency_key"]}).json()["status"] == "rejected"
    assert client.get("/client/assignments", headers=_h(w["ca"])).json()["items"] == []


def test_only_assigned_therapist_can_decide_release(world, real_chunk, monkeypatch) -> None:
    client, w = world
    action = _draft_release(client, w, monkeypatch, real_chunk)
    url, hdr = f"/pending-actions/{action['id']}/approve", {"Idempotency-Key": action["idempotency_key"]}
    for who in ("tb", "owner", "ca", "cb"):
        assert client.post(url, headers=_h(w[who]) | hdr).status_code == 403, who
    assert client.post(url, headers=hdr).status_code == 401
    assert all(i["id"] != action["id"] for i in client.get("/therapists/me/pending-actions", headers=_h(w["tb"])).json()["items"])
    with SessionLocal() as db:
        assert db.query(Assignment).count() == db.query(Assignment).filter(Assignment.pending_action_id != action["id"]).count()


# ---------- access control on the runner ----------

def test_client_sees_only_own_assignments_and_others_denied(world, real_chunk, monkeypatch) -> None:
    client, w = world
    aid = _approved_assignment(client, w, monkeypatch, real_chunk)
    assert client.get("/client/assignments", headers=_h(w["cb"])).json()["items"] == []
    for method, path in (("get", f"/client/assignments/{aid}/exercise"), ("post", f"/client/assignments/{aid}/checkin")):
        kwargs = {"json": {"responses": {"situation": "x", "thought": "y", "feeling_before": 3}}} if method == "post" else {}
        assert getattr(client, method)(path, headers=_h(w["cb"]), **kwargs).status_code == 403   # cross-client
        for who in ("owner", "ta", "tb"):                                                         # owner / therapists
            assert getattr(client, method)(path, headers=_h(w[who]), **kwargs).status_code == 403, who
        assert getattr(client, method)(path, **kwargs).status_code == 401
    for who in ("owner", "ta"):
        assert client.get("/client/assignments", headers=_h(w[who])).status_code == 403
    with SessionLocal() as db:
        assert db.query(Checkin).filter(Checkin.assignment_id == aid).count() == 0


def test_runner_makes_no_model_calls_and_every_response_has_notice(world, real_chunk, monkeypatch) -> None:
    client, w = world
    aid = _approved_assignment(client, w, monkeypatch, real_chunk)
    _forbid_model(monkeypatch)
    ok = {"situation": "Waiting for exam results", "thought": "I will fail", "feeling_before": 7}
    responses = [client.get("/client/dashboard", headers=_h(w["ca"])),
                 client.get("/client/assignments", headers=_h(w["ca"])),
                 client.get(f"/client/assignments/{aid}/exercise", headers=_h(w["ca"])),
                 client.post(f"/client/assignments/{aid}/checkin", headers=_h(w["ca"]), json={"responses": ok})]
    for r in responses:
        assert r.status_code == 200, r.text
        assert r.json()["notice"] == NOTICE and r.json()["crisis_line"] == CRISIS_LINE and "14416" in CRISIS_LINE
    template = responses[2].json()["template"]
    assert {f["id"] for f in template["fields"]} >= {"situation", "thought", "feeling_before"}
    assert responses[3].json()["status"] == "saved"
    with SessionLocal() as db:
        assert db.query(Checkin).filter(Checkin.assignment_id == aid).one().responses_json == ok
    bad = [{"nonsense": "x"}, {"situation": "a"}, {**ok, "feeling_before": 99}]
    for body in bad:
        assert client.post(f"/client/assignments/{aid}/checkin", headers=_h(w["ca"]), json={"responses": body}).status_code == 422


# ---------- risk flow ----------

def test_thirty_labelled_phrases_all_trigger_risk() -> None:
    assert len(RISK_30) == 30
    missed = [t for t in RISK_30 if not risk_scan(t)["flagged"]]
    assert missed == [], f"risk phrases not caught: {missed}"
    assert all(risk_scan(t)["message"] == CRISIS_MESSAGE for t in RISK_30)


def test_hard_negatives_do_not_trigger_layer_1() -> None:
    assert [t for t in HARD_NEGATIVES if risk_check(t)["flagged"]] == []


def test_layer_2_catches_indirect_phrase_that_layer_1_misses() -> None:
    text = "i keep thinking about not waking up tomorrow morning"
    assert risk_check(text)["flagged"] is False
    hit = risk_scan(text)
    assert hit["flagged"] and hit["layer"] == 2 and hit["message"] == CRISIS_MESSAGE


def test_classifier_evaluation_reports_precision_recall() -> None:
    m = evaluate_classifier(embeddings.get_embedder())
    assert m["train"] + m["held_out"] >= 55 and 0 <= m["layer2"]["precision"] <= 1 and 0 <= m["combined"]["recall"] <= 1


@pytest.mark.parametrize("phrase", ["I feel like I can't go on", "मैं मरना चाहता हूँ", "naanu saayabeku anisuttide"])
def test_checkin_risk_path_works_with_model_client_raising(world, real_chunk, monkeypatch, phrase) -> None:
    client, w = world
    aid = _approved_assignment(client, w, monkeypatch, real_chunk)
    _forbid_model(monkeypatch)
    r = client.post(f"/client/assignments/{aid}/checkin", headers=_h(w["ca"]),
                    json={"responses": {"situation": "bad day", "thought": phrase, "feeling_before": 9}})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "crisis" and body["message"] == CRISIS_MESSAGE
    assert "14416" in body["message"] and "1-800-891-4416" in body["message"] and body["notice"] == NOTICE
    with SessionLocal() as db:
        alerts = db.query(Alert).filter(Alert.client_id == w["ca"].id, Alert.type == "risk").all()
        assert any(a.priority == "high" and a.therapist_user_id == w["ta"].id and a.payload["source"] == "checkin" for a in alerts)
        saved = db.query(Checkin).filter(Checkin.assignment_id == aid).all()
        assert len(saved) == 1 and saved[0].flagged is True
    mine = client.get("/therapists/me/alerts", headers=_h(w["ta"])).json()["items"]
    assert any(a["priority"] == "high" for a in mine)
    assert not any(a["client_id"] == w["ca"].id for a in client.get("/therapists/me/alerts", headers=_h(w["tb"])).json()["items"])


def test_contact_form_risk_returns_fixed_message_and_is_not_forwarded(monkeypatch) -> None:
    sent = []
    monkeypatch.setenv("SMTP_HOST", "h"); monkeypatch.setenv("SMTP_USER", "u"); monkeypatch.setenv("SMTP_PASS", "p")
    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: sent.append(1))
    with TestClient(app) as c:
        r = c.post("/practices/contact", json={"name": "A", "email": "a@example.com", "practice": "P",
                                               "message": "I want to kill myself"})
    assert r.json() == {"status": "crisis", "message": CRISIS_MESSAGE} and sent == []


def test_diagnosis_and_supplement_requests_get_no_such_advice(world, real_chunk, monkeypatch) -> None:
    client, w = world
    aid = _approved_assignment(client, w, monkeypatch, real_chunk)
    _forbid_model(monkeypatch)
    r = client.post(f"/client/assignments/{aid}/checkin", headers=_h(w["ca"]), json={"responses": {
        "situation": "Do I have depression? Please diagnose me.", "thought": "Which supplement or medication should I take?",
        "feeling_before": 5}})
    assert r.status_code == 200 and r.json()["status"] == "saved"
    assert clinical_output_violations(json.dumps(r.json())) == []   # nothing generated, nothing advised


@pytest.mark.parametrize("bad", ["The client has major depressive disorder.", "Suggest melatonin 3 mg at night."])
def test_copilot_diagnosis_or_supplement_output_creates_no_release(world, real_chunk, monkeypatch, bad) -> None:
    client, w = world
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "retrieve_knowledge",
                        lambda db, q, a: [Retrieved(id=real_chunk, text="t", similarity=0.9, rrf_score=0.03, title="T")])
    evil = {"summary": bad, "suggestions": [{"text": "Consider a thought record.", "chunk_ids": [real_chunk]}]}
    monkeypatch.setattr(copilot, "call_model", FakeModel([evil, evil]))
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert item["error"] and item["pending_action_id"] is None
    assert not [i for i in client.get("/therapists/me/pending-actions", headers=_h(w["ta"])).json()["items"]
                if i["type"] == "release_exercise"]


def test_client_note_not_wanting_to_be_here_stops_copilot_and_retrieves_nothing(world, monkeypatch) -> None:
    client, w = world
    with SessionLocal() as db:
        db.add(IntakeResponse(booking_id=w["booking_a"].id, client_id=w["ca"].id,
                              answers_json={"note": "Lately I keep having thoughts of not wanting to be here"}))
        db.commit()

    def forbidden(*a, **k):
        raise AssertionError("retrieval must not run on the crisis path")
    monkeypatch.setattr(copilot, "retrieve_knowledge", forbidden)
    model = FakeModel([_briefing(1)])
    monkeypatch.setattr(copilot, "call_model", model)
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert item["status"] == "risk_stop" and model.calls == []
    runs = client.get("/therapists/me/agent-runs", headers=_h(w["ta"])).json()["items"]
    assert "retrieve_knowledge" not in {r["tool"] for r in runs} and "safety_stop" in {r["tool"] for r in runs}
    with SessionLocal() as db:
        assert db.query(PendingAction).filter(PendingAction.type == "release_exercise",
                                              PendingAction.assignee_user_id == w["ta"].id).count() == 0


# ---------- rate limits ----------

def test_client_endpoints_and_contact_form_are_rate_limited(world, monkeypatch) -> None:
    client, w = world
    monkeypatch.setenv("RATE_LIMIT_CLIENT_PER_MIN", "3")
    monkeypatch.setenv("RATE_LIMIT_CONTACT_PER_MIN", "2")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    codes = [client.get("/client/assignments", headers=_h(w["ca"])).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    body = {"name": "A", "email": "a@example.com", "practice": "P", "message": "hello"}
    assert [client.post("/practices/contact", json=body).status_code for _ in range(3)] == [200, 200, 429]


# ---------- hardening: hard negatives, alert text visibility ----------

@pytest.mark.parametrize("phrase", HARD_NEGATIVES_15)
def test_layer1_does_not_fire_on_benign_hard_negatives(phrase) -> None:
    assert risk_check(phrase)["flagged"] is False, phrase


def test_risk_alert_text_only_for_assigned_therapist_and_checkin_flagged(world, real_chunk, monkeypatch, caplog) -> None:
    client, w = world
    aid = _approved_assignment(client, w, monkeypatch, real_chunk)
    _forbid_model(monkeypatch)
    phrase = "I want to end it all tonight"
    with caplog.at_level("DEBUG"):
        r = client.post(f"/client/assignments/{aid}/checkin", headers=_h(w["ca"]),
                        json={"responses": {"situation": "bad day", "thought": phrase, "feeling_before": 9}})
    assert r.json()["status"] == "crisis" and phrase not in caplog.text
    assert phrase not in json.dumps(r.json())          # the client is never shown it back
    with SessionLocal() as db:
        ck = db.query(Checkin).filter(Checkin.assignment_id == aid).one()
        assert ck.flagged is True and ck.responses_json["thought"] == phrase
    mine = [a for a in client.get("/therapists/me/alerts", headers=_h(w["ta"])).json()["items"]
            if a["client_id"] == w["ca"].id]
    assert mine and mine[0]["payload"]["text"] == phrase
    other = client.get("/therapists/me/alerts", headers=_h(w["tb"])).json()["items"]
    assert phrase not in json.dumps(other)


def test_owner_cannot_read_risk_alert_text(world, real_chunk, monkeypatch) -> None:
    client, w = world
    aid = _approved_assignment(client, w, monkeypatch, real_chunk)
    phrase = "I want to end it all tonight"
    client.post(f"/client/assignments/{aid}/checkin", headers=_h(w["ca"]),
                json={"responses": {"situation": "x", "thought": phrase, "feeling_before": 9}})
    owner = _h(w["owner"])
    assert client.get("/therapists/me/alerts", headers=owner).status_code == 403
    for r in (client.get(f"/practices/{w['practice'].id}/agent-runs", headers=owner),
              client.get("/pending-actions", headers=owner)):
        assert phrase not in r.text


def test_intake_and_notes_alerts_carry_text_for_therapist(world, monkeypatch) -> None:
    client, w = world
    with SessionLocal() as db:
        db.add(IntakeResponse(booking_id=w["booking_a"].id, client_id=w["ca"].id,
                              answers_json={"note": "I keep having thoughts of not wanting to be here"}))
        db.commit()
    from backend.app.clinical import raise_risk_alert  # direct: text param is stored only when given
    with SessionLocal() as db:
        a = raise_risk_alert(db, therapist_user_id=w["ta"].id, client_id=w["ca"].id, source="t", source_id=1,
                             match="m", text="hello")
        b = raise_risk_alert(db, therapist_user_id=w["ta"].id, client_id=w["ca"].id, source="t", source_id=1, match="m")
        assert a.payload["text"] == "hello" and "text" not in b.payload
        db.rollback()


def test_inbox_preview_shows_exactly_what_client_gets(world, real_chunk, monkeypatch) -> None:
    client, w = world
    action = _draft_release(client, w, monkeypatch, real_chunk)
    view = action["client_view"]
    assert view["kind"] == "exercise" and view["title"] and view["fields"]
    assert "Nothing else is sent" in view["note"]
    other = client.get("/therapists/me/pending-actions", headers=_h(w["tb"])).json()["items"]
    assert all(i["id"] != action["id"] for i in other)
