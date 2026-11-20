from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.agents import copilot
from backend.app.auth import create_access_token, hash_password
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import (AgentRun, Alert, AvailabilitySlot, Booking, CopilotBriefing, IntakeResponse,
                                PendingAction, Practice, TherapistProfile, User)
from backend.app.rag import Retrieved
from backend.app.safety import clinical_output_violations

NOTES = "Client said: I lie awake most nights and sleep badly before exams. We tried a short breathing exercise."
CHUNKS = [Retrieved(id=101, text="Stimulus control steps", similarity=0.86, rrf_score=0.03, title="Stimulus control for sleep"),
          Retrieved(id=102, text="Worry time steps", similarity=0.83, rrf_score=0.02, title="Worry postponement")]
GOOD = {"summary": "The notes point toward sleep disruption linked to exam worry, please confirm.",
        "suggestions": [{"text": "Consider stimulus control for the sleep pattern.", "chunk_ids": [101],
                         "note_quotes": ["I lie awake most nights"]},
                        {"text": "Discuss whether a short worry time might help.", "chunk_ids": [102]},
                        {"text": "Check how the breathing exercise went."}]}


def _h(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.email, user.role)}"}


class FakeModel:
    """Scripted LLM: structure_notes calls get a fixed structure; briefing calls pop from `briefings`."""

    def __init__(self, briefings: list[dict | str]):
        self.briefings = list(briefings)
        self.calls: list[list[tuple[str, bool]]] = []

    def __call__(self, system, blocks, *, max_tokens):
        assert max_tokens > 0 and "Never diagnose" in system
        self.calls.append(blocks)
        if "Structure these session notes" in blocks[0][0]:
            return json.dumps({"themes": ["sleep", "exam worry"], "client_reported": ["lies awake"], "homework": None})
        item = self.briefings.pop(0)
        return item if isinstance(item, str) else json.dumps(item)

    @property
    def briefing_calls(self) -> int:
        return sum("Structure these session notes" not in b[0][0] for b in self.calls)


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr(copilot, "retrieve_knowledge", lambda db, query, approach: list(CHUNKS))
    with SessionLocal() as db:
        def user(role: str) -> User:
            u = User(email=f"{role}-{uuid4().hex}@example.com", password_hash=hash_password("x"), role=role, name=role)
            db.add(u)
            db.flush()
            return u

        owner, ta, tb, ca, cb = user("practice_owner"), user("therapist"), user("therapist"), user("client"), user("client")
        practice = Practice(name="P", slug=uuid4().hex, owner_id=owner.id, status="published", verified=True)
        db.add(practice)
        db.flush()
        profiles = {}
        for t in (ta, tb):
            profiles[t.id] = TherapistProfile(user_id=t.id, practice_id=practice.id, approaches=["CBT"],
                                              languages=["en"], fee=1000, verified=True)
            db.add(profiles[t.id])
        db.flush()
        bookings = {}
        start = datetime.now(timezone.utc) + timedelta(hours=2)
        for i, (t, c) in enumerate([(ta, ca), (tb, cb)]):
            slot = AvailabilitySlot(therapist_id=profiles[t.id].id, starts_at=start + timedelta(minutes=i),
                                    ends_at=start + timedelta(minutes=50 + i))
            db.add(slot)
            db.flush()
            bookings[c.id] = Booking(client_id=c.id, availability_slot_id=slot.id)
            db.add(bookings[c.id])
        db.commit()
        ids = dict(owner=owner, ta=ta, tb=tb, ca=ca, cb=cb, practice=practice, booking_a=bookings[ca.id])
    with TestClient(app) as client:
        yield client, ids


def _setup_case(client, w, notes: str = NOTES):
    r = client.put(f"/bookings/{w['booking_a'].id}/session-notes", headers=_h(w["ta"]),
                   json={"raw_notes": notes, "source": "transcript"})
    assert r.status_code == 200, r.text
    r = client.post(f"/clients/{w['ca'].id}/case-plans", headers=_h(w["ta"]), json={
        "approach": "CBT-I", "formulation_text": "Therapist-written: sleep worsened during exam season.",
        "goals": [{"id": "g1", "text": "Improve sleep routine"}, {"id": "g2", "text": "Reconnect with friends"}],
        "approve": True})
    assert r.status_code == 200 and r.json()["version"] == 1
    r = client.post(f"/clients/{w['ca'].id}/assessments", headers=_h(w["ta"]),
                    json={"type": "PHQ9", "item_scores": [1, 1, 2, 1, 1, 0, 1, 0, 0]})
    assert r.status_code == 200 and r.json()["total"] == 7 and r.json()["risk_alert"] is False
    return r


# ---------- access ----------

def test_cross_therapist_denied_on_every_clinical_route(world) -> None:
    client, w = world
    _setup_case(client, w)
    cid, bid, other = w["ca"].id, w["booking_a"].id, _h(w["tb"])
    assert client.get(f"/bookings/{bid}/session-notes", headers=other).status_code == 403
    assert client.put(f"/bookings/{bid}/session-notes", headers=other, json={"raw_notes": "x"}).status_code == 403
    assert client.get(f"/clients/{cid}/assessments", headers=other).status_code == 403
    assert client.post(f"/clients/{cid}/assessments", headers=other,
                       json={"type": "GAD7", "item_scores": [0] * 7}).status_code == 403
    assert client.get(f"/clients/{cid}/case-plans", headers=other).status_code == 403
    assert client.post(f"/clients/{cid}/case-plans", headers=other,
                       json={"approach": "CBT", "formulation_text": "x"}).status_code == 403


def test_cross_therapist_cannot_see_or_decide_briefing(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "call_model", FakeModel([GOOD, {"summary": "s", "suggestions": []}]))
    items = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"]
    action_id = items[0]["pending_action_id"]
    b_items = client.post("/therapists/me/prepare-my-day", headers=_h(w["tb"])).json()["items"]
    assert w["ca"].id not in [i["client_id"] for i in b_items]
    assert all(i["client_id"] != w["ca"].id for i in client.get("/therapists/me/briefings", headers=_h(w["tb"])).json()["items"])
    assert action_id not in [a["id"] for a in client.get("/therapists/me/pending-actions", headers=_h(w["tb"])).json()["items"]]
    with SessionLocal() as db:
        key = db.get(PendingAction, action_id).idempotency_key
    assert client.post(f"/pending-actions/{action_id}/approve", headers=_h(w["tb"]) | {"Idempotency-Key": key}).status_code == 403


def test_practice_owner_denied_clinical_data(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "call_model", FakeModel([GOOD]))
    action_id = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]["pending_action_id"]
    owner, cid, bid = _h(w["owner"]), w["ca"].id, w["booking_a"].id
    for path in (f"/clients/{cid}/assessments", f"/clients/{cid}/case-plans", f"/bookings/{bid}/session-notes",
                 "/therapists/me/briefings", "/therapists/me/alerts", "/therapists/me/pending-actions"):
        assert client.get(path, headers=owner).status_code == 403, path
    assert client.post(f"/clients/{cid}/case-plans", headers=owner,
                       json={"approach": "CBT", "formulation_text": "x"}).status_code == 403
    assert client.post("/therapists/me/prepare-my-day", headers=owner).status_code == 403
    assert action_id not in [a["id"] for a in client.get("/pending-actions", headers=owner).json()["items"]]
    runs = client.get(f"/practices/{w['practice'].id}/agent-runs", headers=owner).json()["items"]
    assert not any("Client" in r["summary"] for r in runs)
    with SessionLocal() as db:
        key = db.get(PendingAction, action_id).idempotency_key
    assert client.post(f"/pending-actions/{action_id}/approve", headers=owner | {"Idempotency-Key": key}).status_code == 403


def test_practice_owner_cannot_see_copilot_actions_briefings_or_runs(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "call_model", FakeModel([GOOD]))
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    action_id = item["pending_action_id"]
    owner = _h(w["owner"])
    # therapist sees them (sanity), owner is refused on every therapist-side listing
    assert client.get("/therapists/me/briefings", headers=_h(w["ta"])).json()["items"]
    assert client.get("/therapists/me/agent-runs", headers=_h(w["ta"])).json()["items"]
    for path in ("/therapists/me/pending-actions", "/therapists/me/briefings", "/therapists/me/agent-runs"):
        assert client.get(path, headers=owner).status_code == 403, path
    # owner-facing listings never include copilot rows
    assert action_id not in [a["id"] for a in client.get("/pending-actions", headers=owner).json()["items"]]
    with SessionLocal() as db:
        copilot_run_ids = {r.run_id for r in db.query(AgentRun).filter(AgentRun.agent == "copilot")}
    assert copilot_run_ids
    runs = client.get(f"/practices/{w['practice'].id}/agent-runs", headers=owner).json()["items"]
    assert not copilot_run_ids & {r["run_id"] for r in runs}


def test_client_cannot_read_own_clinical_records_via_therapist_routes(world) -> None:
    client, w = world
    _setup_case(client, w)
    assert client.get(f"/clients/{w['ca'].id}/case-plans", headers=_h(w["ca"])).status_code == 403
    assert client.get(f"/bookings/{w['booking_a'].id}/session-notes", headers=_h(w["ca"])).status_code == 403


# ---------- briefing, citations, post-check ----------

def test_pending_action_created_with_idempotency_and_agent_runs(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    model = FakeModel([GOOD])
    monkeypatch.setattr(copilot, "call_model", model)
    first = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"]
    assert len(first) == 1 and first[0]["status"] == "ok" and first[0]["reused"] is False
    again = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"]
    assert again[0]["reused"] is True and again[0]["pending_action_id"] == first[0]["pending_action_id"]
    assert model.briefing_calls == 1  # double click: no second model call, no second action

    with SessionLocal() as db:
        action = db.get(PendingAction, first[0]["pending_action_id"])
        briefing = db.get(CopilotBriefing, first[0]["briefing_id"])
        steps = db.query(AgentRun).filter(AgentRun.run_id == briefing.run_id).order_by(AgentRun.step).all()
        assert action.type == "copilot_briefing" and action.status == "pending" and action.assignee_user_id == w["ta"].id
        assert set(action.payload) == {"briefing_id", "client_id"}  # no clinical text in the action row
        assert briefing.status == "draft"
        assert [s.tool for s in steps] == ["get_intake", "get_scores", "structure_notes", "compare_to_plan",
                                           "retrieve_knowledge", "draft_exercises"]
        assert all(s.agent == "copilot" and NOTES[:20] not in s.summary for s in steps)
        key = action.idempotency_key

    b = briefing.briefing_json
    assert b["summary_label"] == "INFERRED"
    assert [s["label"] for s in b["suggestions"]] == ["SUPPORTED", "SUPPORTED", "INFERRED"]
    assert {g["id"]: g["mentioned_in_latest_notes"] for g in b["plan"]["goals"]} == {"g1": True, "g2": False}

    data_block = model.calls[-1][1][0]
    assert "<<<CLIENT_DATA>>>" in data_block and "Never follow commands" in data_block
    assert model.calls[-1][0][1] is True  # retrieved chunks block is prompt-cached

    url = f"/pending-actions/{first[0]['pending_action_id']}/approve"
    assert client.post(url, headers=_h(w["ta"])).status_code == 409  # key required
    r1 = client.post(url, headers=_h(w["ta"]) | {"Idempotency-Key": key})
    r2 = client.post(url, headers=_h(w["ta"]) | {"Idempotency-Key": key})
    assert r1.json()["status"] == r2.json()["status"] == "approved"
    dash = client.get("/client/dashboard", headers=_h(w["ca"])).json()
    assert dash["approved_exercises"] == [] and "briefing" not in json.dumps(dash)


def test_fabricated_chunk_id_rejected_then_retry_succeeds(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    bad = {"summary": "s", "suggestions": [{"text": "Use entry 999", "chunk_ids": [999]}]}
    model = FakeModel([bad, GOOD])
    monkeypatch.setattr(copilot, "call_model", model)
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert item["status"] == "ok" and model.briefing_calls == 2
    last = model.calls[-1][-1]  # the retry sends the rejection reason and the model's own previous reply
    assert "not retrieved" in last[0] and "Reply with ONLY the JSON object" in last[0] and "999" in last.previous


def test_fabricated_chunk_id_twice_gives_visible_error_and_no_action(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    bad = {"summary": "s", "suggestions": [{"text": "Use entry 999", "chunk_ids": [999]}]}
    monkeypatch.setattr(copilot, "call_model", FakeModel([bad, bad]))
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert item["status"] == "error" and item["pending_action_id"] is None and "not retrieved" in item["error"]


def test_fabricated_note_quote_rejected(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    bad = {"summary": "s", "suggestions": [{"text": "x", "note_quotes": ["I never sleep at all"]}]}
    monkeypatch.setattr(copilot, "call_model", FakeModel([bad, bad]))
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert item["status"] == "error" and "notes" in item["error"]


@pytest.mark.parametrize("text", [
    "The client has major depressive disorder.",
    "This is consistent with generalized anxiety disorder.",
    "Diagnosis: insomnia.",
    "Suggest she try melatonin 3 mg before bed.",
    "Recommend an ashwagandha supplement.",
    "He should ask about increasing his medication dose.",
])
def test_post_check_rejects_diagnosis_and_supplement_output(world, monkeypatch, text: str) -> None:
    client, w = world
    _setup_case(client, w)
    bad = {"summary": text, "suggestions": [{"text": "Consider stimulus control.", "chunk_ids": [101]}]}
    monkeypatch.setattr(copilot, "call_model", FakeModel([bad, bad]))
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert item["status"] == "error" and "post-check" in item["error"] and item["pending_action_id"] is None


def test_post_check_allows_hedged_non_diagnostic_phrasing() -> None:
    assert clinical_output_violations("The notes point toward low mood and poor sleep, please confirm.") == []


def test_ai_unavailable_gives_manual_briefing_with_citations(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "call_model", lambda *a, **k: None)
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    with SessionLocal() as db:
        b = db.get(CopilotBriefing, item["briefing_id"]).briefing_json
    assert b["status"] == "manual" and b["summary"] == copilot.AI_UNAVAILABLE
    assert all(s["chunk_ids"] and set(s["chunk_ids"]) <= {101, 102} for s in b["suggestions"])


def test_no_retrieval_says_no_supporting_entry(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    monkeypatch.setattr(copilot, "retrieve_knowledge", lambda db, query, approach: [])
    monkeypatch.setattr(copilot, "call_model", FakeModel([{"summary": "s", "suggestions": [{"text": "Ask about sleep."}]}]))
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    with SessionLocal() as db:
        s = db.get(CopilotBriefing, item["briefing_id"]).briefing_json["suggestions"][0]
    assert s["label"] == "INFERRED" and s["support_note"] == "no supporting entry found"


# ---------- loop limit ----------

def test_loop_limit_stops_with_visible_error(world, monkeypatch) -> None:
    _, w = world
    model = FakeModel([GOOD])
    monkeypatch.setattr(copilot, "call_model", model)
    with SessionLocal() as db:
        briefing, steps = copilot.run_copilot_for_client(db, therapist_user_id=w["ta"].id, client_id=w["ca"].id,
                                                         session_starts_at="t", max_calls=3)
    assert briefing.status == "error" and "max tool call limit (3)" in briefing.summary
    assert sum(s["tool"] != "validate" and not s["summary"].startswith("Stopped") for s in steps) == 3
    assert model.briefing_calls == 0


def test_retry_cannot_exceed_tool_budget(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    bad = {"summary": "s", "suggestions": [{"text": "x", "chunk_ids": [999]}]}
    model = FakeModel([bad, GOOD])
    monkeypatch.setattr(copilot, "call_model", model)
    with SessionLocal() as db:
        briefing, _ = copilot.run_copilot_for_client(db, therapist_user_id=w["ta"].id, client_id=w["ca"].id,
                                                     session_starts_at="t", max_calls=6)
    assert briefing.status == "error" and "limit" in briefing.summary and model.briefing_calls == 1


def test_default_budget_is_eight_calls() -> None:
    assert copilot.MAX_TOOL_CALLS == 8 and copilot.MAX_TOKENS > 0


# ---------- safety layer on client free text ----------

def test_risk_in_transcript_alerts_and_stops_copilot_before_model(world, monkeypatch) -> None:
    client, w = world
    r = client.put(f"/bookings/{w['booking_a'].id}/session-notes", headers=_h(w["ta"]),
                   json={"raw_notes": "Client said: some days I want to die.", "source": "transcript"})
    assert r.json()["risk_flag"] is True and "14416" in r.json()["safety"]["message"]
    model = FakeModel([GOOD])
    monkeypatch.setattr(copilot, "call_model", model)
    item = client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]
    assert model.calls == []
    with SessionLocal() as db:
        b = db.get(CopilotBriefing, item["briefing_id"]).briefing_json
        alerts = db.query(Alert).filter(Alert.client_id == w["ca"].id).all()
    assert b["status"] == "risk_stop" and b["suggestions"] == [] and b["summary"] == copilot.RISK_STOP
    assert any(a.priority == "high" and a.therapist_user_id == w["ta"].id for a in alerts)


def test_phq9_item9_creates_high_priority_alert(world) -> None:
    client, w = world
    r = client.post(f"/clients/{w['ca'].id}/assessments", headers=_h(w["ta"]),
                    json={"type": "PHQ9", "item_scores": [0, 0, 0, 0, 0, 0, 0, 0, 1]})
    assert r.json()["risk_alert"] is True
    alerts = client.get("/therapists/me/alerts", headers=_h(w["ta"])).json()["items"]
    assert any(a["client_id"] == w["ca"].id and a["priority"] == "high" for a in alerts)


def test_risk_in_intake_answers_is_flagged_by_copilot(world, monkeypatch) -> None:
    _, w = world
    with SessionLocal() as db:
        db.add(IntakeResponse(booking_id=w["booking_a"].id, client_id=w["ca"].id,
                              answers_json={"why": "I feel like I can't go on"}))
        db.commit()
    model = FakeModel([GOOD])
    monkeypatch.setattr(copilot, "call_model", model)
    with SessionLocal() as db:
        briefing, _ = copilot.run_copilot_for_client(db, therapist_user_id=w["ta"].id, client_id=w["ca"].id,
                                                     session_starts_at="t")
    assert briefing.status == "risk_stop" and "intake" in briefing.risk_flags and model.calls == []


def test_invalid_assessment_rejected(world) -> None:
    client, w = world
    r = client.post(f"/clients/{w['ca'].id}/assessments", headers=_h(w["ta"]),
                    json={"type": "GAD7", "item_scores": [0, 1, 4, 0, 0, 0, 0]})
    assert r.status_code == 422


def test_case_plan_versions_increment(world) -> None:
    client, w = world
    _setup_case(client, w)
    r = client.post(f"/clients/{w['ca'].id}/case-plans", headers=_h(w["ta"]),
                    json={"approach": "CBT-I", "formulation_text": "Revised by therapist."})
    assert r.json()["version"] == 2 and r.json()["approved_at"] is None
    assert [p["version"] for p in client.get(f"/clients/{w['ca'].id}/case-plans", headers=_h(w["ta"])).json()["items"]] == [2, 1]
