from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app import practice_setup
from backend.app.auth import create_access_token, hash_password
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import (Practice, PracticeInvite, TherapistProfile, User, VerificationDocument)
from backend.scripts import seed as seed_mod

client = TestClient(app)
PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
DETAILS = {"city": "Pune", "address": "5 Test Road, Pune", "approach": "CBT-informed, skill-building",
           "specialisations": ["stress", "sleep"], "languages": ["en", "hi"], "session_formats": ["online", "in_person"],
           "fee_min": 1000, "fee_max": 1800, "hours": "Mon-Fri 10-17", "years_operating": 4}


@pytest.fixture(autouse=True)
def private_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("FAKE_LLM", "1")
    return tmp_path / "verification"


def _user(db, role: str, tag: str) -> User:
    u = User(email=f"{tag}-{uuid4().hex[:8]}@example.com", password_hash=hash_password("x" * 12), role=role, name=tag.title())
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def world():
    with SessionLocal() as db:
        users = {t: _user(db, r, t) for t, r in (("owner", "practice_owner"), ("owner_b", "practice_owner"), ("admin", "admin"),
                                                  ("client", "client"), ("ther", "therapist"), ("invitee", "therapist"),
                                                  ("other_ther", "therapist"))}
        other = Practice(name="Other Practice", slug=uuid4().hex, owner_id=users["owner_b"].id, status="draft", verified=False, page_json="{}")
        theirs = Practice(name="Therapist Home", slug=uuid4().hex, owner_id=users["owner_b"].id, status="published", verified=True,
                          verification_status="verified", page_json="{}")
        db.add_all([other, theirs])
        db.flush()
        prof = TherapistProfile(user_id=users["other_ther"].id, practice_id=theirs.id, bio="", fee=1000, languages=["en"], verified=False)
        db.add(prof)
        db.commit()
        emails = {k: (u.email, u.role) for k, u in users.items()}
        ids = [u.id for u in users.values()]
        pids = [other.id, theirs.id]
        info = {"other_practice": other.id, "other_profile": prof.id}
    heads = {k: {"Authorization": f"Bearer {create_access_token(e, r)}"} for k, (e, r) in emails.items()}
    w = {"h": heads, "emails": {k: e for k, (e, _) in emails.items()}, "created": [], **info}
    yield w
    with SessionLocal() as db:
        all_pids = pids + w["created"]
        db.execute(delete(VerificationDocument).where(VerificationDocument.owner_type == "practice", VerificationDocument.owner_id.in_(all_pids)))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.execute(delete(Practice).where(Practice.id.in_(all_pids)))
        db.commit()


def _create(w, who="owner", name="Setup Practice") -> int:
    r = client.post("/owner/practices", headers=w["h"][who], json={"name": name, "city": "Pune"})
    assert r.status_code == 201, r.text
    w["created"].append(r.json()["id"])
    return r.json()["id"]


def _details(w, pid, who="owner", **over):
    return client.put(f"/owner/practices/{pid}/details", headers=w["h"][who], json=DETAILS | over)


def _doc(w, pid, who="owner", doc_type="business_registration", content=PDF, name="reg.pdf"):
    return client.post(f"/owner/practices/{pid}/documents", headers=w["h"][who], data={"doc_type": doc_type},
                       files={"file": (name, content, "application/pdf")})


def _ready(w) -> int:
    pid = _create(w)
    assert _details(w, pid).status_code == 200
    assert _doc(w, pid).status_code == 201
    assert client.post(f"/owner/practices/{pid}/page/generate", headers=w["h"]["owner"], json={}).status_code == 200
    return pid


def _verify(w, pid):
    assert client.post(f"/owner/practices/{pid}/submit", headers=w["h"]["owner"]).status_code == 200
    r = client.post(f"/admin/practices/{pid}/review", headers=w["h"]["admin"], json={"decision": "verified"})
    assert r.status_code == 200, r.text


def _invite(w, pid, email, key=None, who="owner"):
    with patch.object(practice_setup, "_send_invite_email", return_value="sent") as send:
        r = client.post(f"/owner/practices/{pid}/invites", headers=w["h"][who] | {"Idempotency-Key": key or uuid4().hex}, json={"email": email})
    token = send.call_args.args[3].split("token=")[1] if send.called else None
    return r, token


# ---------- access control ----------

OWNER_ROUTES = [
    ("get", "/owner/practices/{id}/setup", None), ("put", "/owner/practices/{id}/details", DETAILS),
    ("put", "/owner/practices/{id}/page", {"tagline": "t", "text": "x" * 60}),
    ("post", "/owner/practices/{id}/page/generate", {}), ("post", "/owner/practices/{id}/submit", None),
    ("post", "/owner/practices/{id}/publish", None), ("post", "/owner/practices/{id}/invites", {"email": "a@example.com"}),
    ("post", "/owner/practices/{id}/invites/1/revoke", None), ("delete", "/owner/practices/{id}/team/1", None),
    ("delete", "/owner/practices/{id}/documents/1", None),
]


def _call(method, path, headers, body):
    return client.request(method.upper(), path, headers=headers | {"Idempotency-Key": "k1"}, json=body)


@pytest.mark.parametrize("method,path,body", OWNER_ROUTES)
def test_owner_cannot_touch_another_owners_practice(world, method, path, body) -> None:
    r = _call(method, path.format(id=world["other_practice"]), world["h"]["owner"], body)
    assert r.status_code == 404, (path, r.text)


@pytest.mark.parametrize("who", ["ther", "client", "admin"])
@pytest.mark.parametrize("method,path,body", OWNER_ROUTES)
def test_other_roles_get_403_on_owner_routes(world, who, method, path, body) -> None:
    assert _call(method, path.format(id=world["other_practice"]), world["h"][who], body).status_code == 403


def test_owner_routes_need_login_and_upload_needs_owner(world) -> None:
    assert client.get("/owner/practices/1/setup").status_code == 401
    pid = _create(world)
    for who in ("ther", "client", "owner_b"):
        assert _doc(world, pid, who).status_code in (403, 404)
    assert client.post("/owner/practices", headers=world["h"]["ther"], json={"name": "X", "city": "Y"}).status_code == 403


def test_admin_routes_are_admin_only(world) -> None:
    pid = _create(world)
    for who in ("owner", "ther", "client"):
        assert client.get(f"/admin/practices/{pid}/verification", headers=world["h"][who]).status_code == 403
        assert client.post(f"/admin/practices/{pid}/review", headers=world["h"][who], json={"decision": "verified"}).status_code == 403


def test_owner_cannot_reach_clinical_data(world) -> None:
    h = world["h"]["owner"]
    for method, path, body in (("get", "/clients/1/assessments", None), ("post", "/clients/1/case-plans", {}),
                               ("get", "/therapists/me/bookings", None), ("get", "/therapists/me/verification", None),
                               ("get", "/admin/therapists/1/verification", None)):
        assert client.request(method.upper(), path, headers=h, json=body).status_code == 403, path


# ---------- details ----------

def test_details_roundtrip_validation_and_lock(world) -> None:
    pid = _create(world)
    assert client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()["missing"][0].startswith("Details")
    r = _details(world, pid)
    assert r.status_code == 200 and r.json()["details"]["specialisations"] == ["stress", "sleep"]
    for bad in ({"languages": ["fr"]}, {"fee_min": 0}, {"session_formats": []}, {"years_operating": -1}, {"city": None}, {"slug": "x"},
                {"fee_min": 2000, "fee_max": 1000}):
        assert _details(world, pid, **bad).status_code == 422, bad
    assert _doc(world, pid).status_code == 201
    client.post(f"/owner/practices/{pid}/page/generate", headers=world["h"]["owner"], json={})
    assert client.post(f"/owner/practices/{pid}/submit", headers=world["h"]["owner"]).status_code == 200
    assert _details(world, pid, city="Goa").status_code == 409  # locked while under review


# ---------- documents ----------

def test_documents_follow_the_same_upload_rules(world, private_uploads) -> None:
    pid = _create(world)
    r = _doc(world, pid)
    assert r.status_code == 201 and r.json()["doc_type"] == "business_registration"
    with SessionLocal() as db:
        key = db.scalar(select(VerificationDocument.storage_key).where(VerificationDocument.id == r.json()["id"]))
    assert len(key) == 32 and (private_uploads / key).is_file() and "reg" not in key
    assert _doc(world, pid, doc_type="degree_certificate").status_code == 422
    assert _doc(world, pid, content=b"MZ not a pdf").status_code == 415
    assert _doc(world, pid, content=b"%PDF-" + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert _doc(world, pid, content=PDF, name="x.exe").status_code == 415
    for _ in range(9):
        assert _doc(world, pid, doc_type="address_proof").status_code == 201
    assert _doc(world, pid).status_code == 409  # 10 files max
    setup = client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()
    assert {d["doc_type"]: d["uploaded"] for d in setup["required_documents"]} == {
        "business_registration": True, "clinic_license_or_gst": False, "address_proof": True}


def test_practice_document_access(world) -> None:
    pid = _create(world)
    doc_id = _doc(world, pid).json()["id"]
    url = f"/verification-documents/{doc_id}/download"
    ok = client.get(url, headers=world["h"]["owner"])
    assert ok.status_code == 200 and ok.content == PDF
    assert ok.headers["cache-control"] == "private, no-store" and ok.headers["x-content-type-options"] == "nosniff"
    assert client.get(url, headers=world["h"]["admin"]).status_code == 200
    assert client.get(url, headers=world["h"]["owner_b"]).status_code == 404
    for who in ("ther", "other_ther", "invitee", "client"):
        assert client.get(url, headers=world["h"][who]).status_code == 403, who
    assert client.get(url).status_code == 401
    assert client.delete(f"/owner/practices/{world['other_practice']}/documents/{doc_id}", headers=world["h"]["owner"]).status_code == 404


def test_owner_cannot_download_therapist_documents(world) -> None:
    with SessionLocal() as db:
        doc = practice_setup.store_file(db, "therapist", world["other_profile"], "degree_certificate", "d.pdf", PDF)
        db.commit()
        doc_id = doc.id
    for who in ("owner", "owner_b"):
        assert client.get(f"/verification-documents/{doc_id}/download", headers=world["h"][who]).status_code == 403
    assert client.get(f"/verification-documents/{doc_id}/download", headers=world["h"]["other_ther"]).status_code == 200
    with SessionLocal() as db:
        db.execute(delete(VerificationDocument).where(VerificationDocument.id == doc_id))
        db.commit()


def test_owner_deletes_document_and_file_is_removed(world, private_uploads) -> None:
    pid = _create(world)
    r = _doc(world, pid).json()
    assert client.delete(f"/owner/practices/{pid}/documents/{r['id']}", headers=world["h"]["owner"]).status_code == 204
    assert list(private_uploads.iterdir()) == []


# ---------- verification flow ----------

def test_submit_requires_details_document_and_page(world) -> None:
    pid = _create(world)
    h = world["h"]["owner"]
    r = client.post(f"/owner/practices/{pid}/submit", headers=h)
    assert r.status_code == 422 and all(w in r.json()["detail"] for w in ("Details", "Documents", "Page"))
    _details(world, pid)
    _doc(world, pid)
    assert "Page" in client.post(f"/owner/practices/{pid}/submit", headers=h).json()["detail"]
    client.put(f"/owner/practices/{pid}/page", headers=h, json={"tagline": "Calm help.", "text": "We offer calm, paced sessions."})
    setup = client.get(f"/owner/practices/{pid}/setup", headers=h).json()
    assert setup["missing"] == [] and setup["can_submit"]
    done = client.post(f"/owner/practices/{pid}/submit", headers=h).json()
    assert done["verification_status"] == "submitted" and done["submitted_at"] and not done["verified"]
    assert client.post(f"/owner/practices/{pid}/submit", headers=h).status_code == 409


def test_review_flow_changes_requested_then_verified(world) -> None:
    pid = _ready(world)
    h, a = world["h"]["owner"], world["h"]["admin"]
    client.post(f"/owner/practices/{pid}/submit", headers=h)
    detail = client.get(f"/admin/practices/{pid}/verification", headers=a).json()
    assert detail["details"]["city"] == "Pune" and len(detail["documents"]) == 1 and detail["page"]["has_draft"]
    for body in ({"decision": "changes_requested"}, {"decision": "rejected", "note": ""}, {"decision": "maybe"}):
        assert client.post(f"/admin/practices/{pid}/review", headers=a, json=body).status_code == 422
    r = client.post(f"/admin/practices/{pid}/review", headers=a, json={"decision": "changes_requested", "note": "Add an address proof."})
    assert r.json()["status"] == "changes_requested" and r.json()["verified"] is False
    setup = client.get(f"/owner/practices/{pid}/setup", headers=h).json()
    assert setup["reviewer_note"] == "Add an address proof." and setup["reviewed_at"] and setup["can_edit_documents"]
    assert _doc(world, pid, doc_type="address_proof").status_code == 201
    client.post(f"/owner/practices/{pid}/submit", headers=h)
    r = client.post(f"/admin/practices/{pid}/review", headers=a, json={"decision": "verified"})
    assert r.json()["status"] == "verified" and r.json()["verified"] is True
    assert client.post(f"/admin/practices/{pid}/review", headers=a, json={"decision": "rejected", "note": "x"}).status_code == 409  # not submitted
    assert client.get(f"/admin/practices/{pid}/verification", headers=a).status_code == 200


def test_rejected_practice_is_locked(world) -> None:
    pid = _ready(world)
    client.post(f"/owner/practices/{pid}/submit", headers=world["h"]["owner"])
    client.post(f"/admin/practices/{pid}/review", headers=world["h"]["admin"], json={"decision": "rejected", "note": "Not eligible."})
    h = world["h"]["owner"]
    assert client.post(f"/owner/practices/{pid}/submit", headers=h).status_code == 409
    assert _details(world, pid, city="Goa").status_code == 409
    assert _doc(world, pid).status_code == 409
    assert client.put(f"/owner/practices/{pid}/page", headers=h, json={"tagline": "t", "text": "plain text"}).status_code == 409


def test_legacy_admin_toggle_keeps_status_in_sync(world) -> None:
    pid = _create(world)
    r = client.post(f"/admin/practices/{pid}/verify", headers=world["h"]["admin"], json={"verified": True})
    assert r.json()["verified"] is True
    assert client.get(f"/admin/practices/{pid}/verification", headers=world["h"]["admin"]).json()["verification_status"] == "verified"


# ---------- page draft ----------

def test_ai_draft_is_stored_with_its_inputs_and_regeneration_needs_confirm(world) -> None:
    pid = _create(world)
    h = world["h"]["owner"]
    assert client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={}).status_code == 422  # details incomplete
    _details(world, pid)
    r = client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={})
    assert r.status_code == 200
    page = r.json()
    assert page["source"] == "ai" and page["text"] and page["tagline"] and page["inputs"]["specialisations"] == ["stress", "sleep"]
    assert "address" not in page["inputs"] and page["inputs_changed"] is False
    edited = client.put(f"/owner/practices/{pid}/page", headers=h, json={"tagline": "My own line.", "text": "My own words, **bold** and:\n- one"})
    assert edited.json()["source"] == "edited" and edited.json()["text"].startswith("My own words")
    # regeneration never overwrites without a confirm
    assert client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={}).status_code == 409
    assert client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={"confirm": False}).status_code == 409
    assert client.get(f"/owner/practices/{pid}/setup", headers=h).json()["page"]["text"].startswith("My own words")
    again = client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={"confirm": True})
    assert again.status_code == 200 and again.json()["source"] == "ai" and not again.json()["text"].startswith("My own words")
    _details(world, pid, hours="Tue-Sat 9-13")
    assert client.get(f"/owner/practices/{pid}/setup", headers=h).json()["page"]["inputs_changed"] is True


def test_ai_unavailable_or_over_budget_leaves_the_manual_path_open(world) -> None:
    pid = _create(world)
    _details(world, pid)
    h = world["h"]["owner"]
    with patch.object(practice_setup.copilot, "call_model", return_value=None):
        r = client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={})
    assert r.status_code == 503 and r.json()["detail"] == "AI unavailable, manual workflow open."
    saved = client.put(f"/owner/practices/{pid}/page", headers=h, json={"tagline": "Calm help.", "text": "Written by hand."})
    assert saved.status_code == 200 and saved.json()["source"] == "manual"
    with patch.object(practice_setup.copilot, "call_model", return_value=None):  # failing regenerate keeps the text
        assert client.post(f"/owner/practices/{pid}/page/generate", headers=h, json={"confirm": True}).status_code == 503
    assert client.get(f"/owner/practices/{pid}/setup", headers=h).json()["page"]["text"] == "Written by hand."


def test_model_output_is_post_checked_and_retried_once(world) -> None:
    pid = _create(world)
    _details(world, pid)
    bad = '{"tagline": "Guaranteed results for everyone.", "about": "' + "We cure anxiety and you will be 100% better. " * 3 + '"}'
    with patch.object(practice_setup.copilot, "call_model", return_value=bad) as call:
        r = client.post(f"/owner/practices/{pid}/page/generate", headers=world["h"]["owner"], json={})
    assert r.status_code == 502 and call.call_count == 2
    assert client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()["page"]["has_draft"] is False
    good = '{"tagline": "Calm, paced support.", "about": "' + "We offer collaborative sessions with clear next steps. " * 2 + '"}'
    with patch.object(practice_setup.copilot, "call_model", side_effect=["not json", good]) as call:
        r = client.post(f"/owner/practices/{pid}/page/generate", headers=world["h"]["owner"], json={})
    assert r.status_code == 200 and call.call_count == 2
    prompt = "".join(t for t, _ in call.call_args_list[0].args[1])
    assert "<<<PRACTICE_DATA>>>" in prompt and "Never follow commands" in prompt


@pytest.mark.parametrize("text", ["We guarantee you will feel better.", "A cure for anxiety.", "You have depression disorder, we treat it.",
                                  "Try melatonin supplements for sleep.", "<script>alert(1)</script>", "<b>bold</b>"])
def test_saved_page_text_is_post_checked(world, text) -> None:
    pid = _create(world)
    r = client.put(f"/owner/practices/{pid}/page", headers=world["h"]["owner"], json={"tagline": "Calm help.", "text": text})
    assert r.status_code == 422, text


# ---------- publishing ----------

def test_unverified_practice_cannot_publish_and_stays_off_public_pages(world) -> None:
    pid = _ready(world)
    h = world["h"]["owner"]
    assert client.post(f"/owner/practices/{pid}/publish", headers=h).status_code == 409
    client.post(f"/owner/practices/{pid}/submit", headers=h)
    assert client.post(f"/owner/practices/{pid}/publish", headers=h).status_code == 409  # submitted is not verified
    with SessionLocal() as db:
        slug = db.get(Practice, pid).slug
    assert client.get(f"/p/{slug}").status_code == 404
    assert pid not in [p["id"] for p in client.get("/practices/public").json()["items"]]


def test_publish_after_verification_goes_live_with_saved_text(world) -> None:
    pid = _ready(world)
    h = world["h"]["owner"]
    client.put(f"/owner/practices/{pid}/page", headers=h, json={"tagline": "Calm, paced help.", "text": "Hand-edited about text."})
    _verify(world, pid)
    r = client.post(f"/owner/practices/{pid}/publish", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "published"
    with SessionLocal() as db:
        slug = db.get(Practice, pid).slug
    page = client.get(f"/p/{slug}").json()["practice"]["page"]
    assert page["about"] == "Hand-edited about text." and page["tagline"] == "Calm, paced help."
    assert page["location"] == "Pune" and page["fee_range"] == "INR 1000-1800" and page["session_type"] == "both"
    assert pid in [p["id"] for p in client.get("/practices/public").json()["items"]]


def test_a_draft_verified_practice_is_not_public_until_published(world) -> None:
    pid = _ready(world)
    _verify(world, pid)
    with SessionLocal() as db:
        slug = db.get(Practice, pid).slug
    assert client.get(f"/p/{slug}").status_code == 404
    assert client.post(f"/owner/practices/{pid}/publish", headers=world["h"]["owner"]).status_code == 200
    assert client.get(f"/p/{slug}").status_code == 200


# ---------- invites ----------

def test_invite_stores_only_a_hash_and_is_idempotent(world) -> None:
    pid = _create(world)
    key = uuid4().hex
    r, token = _invite(world, pid, "New.Person@Example.com", key)
    assert r.status_code == 201 and r.json()["status"] == "pending" and r.json()["email"] == "new.person@example.com"
    assert r.json()["email_status"] == "sent" and "token" not in r.text
    exp = datetime.fromisoformat(r.json()["expires_at"])
    assert timedelta(days=6, hours=23) < exp - datetime.now(timezone.utc) <= timedelta(days=7)
    with SessionLocal() as db:
        row = db.get(PracticeInvite, r.json()["id"])
        assert row.token_hash != token and len(row.token_hash) == 64 and token not in (row.token_hash, row.email)
    again, token2 = _invite(world, pid, "new.person@example.com", key)  # replay: same invite, nothing sent
    assert again.status_code == 200 and again.json()["id"] == r.json()["id"] and again.json()["email_status"] == "already_sent" and token2 is None
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(PracticeInvite).where(PracticeInvite.practice_id == pid)) == 1
    assert _invite(world, pid, "new.person@example.com")[0].status_code == 409  # already pending
    assert client.post(f"/owner/practices/{pid}/invites", headers=world["h"]["owner"], json={"email": "z@example.com"}).status_code == 422
    assert client.post(f"/owner/practices/{pid}/invites", headers=world["h"]["owner"] | {"Idempotency-Key": "k"}, json={"email": "nope"}).status_code == 422
    setup = client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()
    assert [i["email"] for i in setup["invites"]] == ["new.person@example.com"]


def test_accept_links_the_therapist_and_the_token_is_single_use(world) -> None:
    pid = _create(world)
    _details(world, pid)
    r, token = _invite(world, pid, world["emails"]["invitee"])
    h = world["h"]["invitee"]
    prev = client.post("/invitations/preview", headers=h, json={"token": token})
    assert prev.status_code == 200 and prev.json()["practice_name"] == "Setup Practice"
    acc = client.post("/invitations/accept", headers=h, json={"token": token})
    assert acc.status_code == 200 and acc.json()["practice_id"] == pid
    with SessionLocal() as db:
        profile = db.scalar(select(TherapistProfile).where(TherapistProfile.id == acc.json()["therapist_id"]))
        assert profile.practice_id == pid and profile.verified is False  # linked, but not verified by joining
    assert client.post("/invitations/accept", headers=h, json={"token": token}).status_code == 410  # reused
    assert client.post("/invitations/preview", headers=h, json={"token": token}).status_code == 410
    team = client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()["team"]
    assert [m["email"] for m in team] == [world["emails"]["invitee"]] and set(team[0]) == {"id", "name", "email", "verified"}
    assert client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()["invites"] == []


def test_wrong_email_expired_revoked_and_unknown_tokens_fail(world) -> None:
    pid = _create(world)
    _, token = _invite(world, pid, world["emails"]["invitee"])
    other = world["h"]["other_ther"]
    for path in ("accept", "preview", "decline"):
        assert client.post(f"/invitations/{path}", headers=other, json={"token": token}).status_code == 404, path
        assert client.post(f"/invitations/{path}", headers=world["h"]["invitee"], json={"token": "x" * 43}).status_code == 404
    with SessionLocal() as db:  # wrong-email attempts must not consume the token
        assert db.scalar(select(PracticeInvite.status).where(PracticeInvite.practice_id == pid)) == "pending"
        db.execute(PracticeInvite.__table__.update().where(PracticeInvite.practice_id == pid)
                   .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    assert client.post("/invitations/accept", headers=world["h"]["invitee"], json={"token": token}).status_code == 410
    assert "expired" in client.post("/invitations/accept", headers=world["h"]["invitee"], json={"token": token}).json()["detail"]
    assert client.get(f"/owner/practices/{pid}/setup", headers=world["h"]["owner"]).json()["invites"][0]["status"] == "expired"
    # revoked
    with SessionLocal() as db:
        db.execute(delete(PracticeInvite).where(PracticeInvite.practice_id == pid))
        db.commit()
    r, token3 = _invite(world, pid, world["emails"]["invitee"])
    assert client.post(f"/owner/practices/{pid}/invites/{r.json()['id']}/revoke", headers=world["h"]["owner"]).json()["status"] == "revoked"
    assert client.post("/invitations/accept", headers=world["h"]["invitee"], json={"token": token3}).status_code == 410
    assert client.post(f"/owner/practices/{pid}/invites/{r.json()['id']}/revoke", headers=world["h"]["owner"]).status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(TherapistProfile).where(TherapistProfile.user_id == db.scalar(
            select(User.id).where(User.email == world["emails"]["invitee"])))) == 0


def test_only_therapists_use_invitations_and_other_owners_cannot_revoke(world) -> None:
    pid = _create(world)
    r, token = _invite(world, pid, world["emails"]["invitee"])
    for who in ("owner", "client", "admin"):
        assert client.post("/invitations/accept", headers=world["h"][who], json={"token": token}).status_code == 403
    assert client.post("/invitations/accept", json={"token": token}).status_code == 401
    assert client.post(f"/owner/practices/{pid}/invites/{r.json()['id']}/revoke", headers=world["h"]["owner_b"]).status_code == 404
    assert _invite(world, pid, "a@example.com", who="owner_b")[0].status_code == 404


def test_decline_and_remove_from_team(world) -> None:
    pid = _create(world)
    r, token = _invite(world, pid, world["emails"]["invitee"])
    assert client.post("/invitations/decline", headers=world["h"]["invitee"], json={"token": token}).json() == {"status": "declined"}
    assert client.post("/invitations/accept", headers=world["h"]["invitee"], json={"token": token}).status_code == 410
    _, token = _invite(world, pid, world["emails"]["invitee"])
    tid = client.post("/invitations/accept", headers=world["h"]["invitee"], json={"token": token}).json()["therapist_id"]
    h = world["h"]["owner"]
    assert client.delete(f"/owner/practices/{pid}/team/{world['other_profile']}", headers=h).status_code == 404  # another practice's therapist
    assert client.delete(f"/owner/practices/{pid}/team/{tid}", headers=h).status_code == 204
    assert client.get(f"/owner/practices/{pid}/setup", headers=h).json()["team"] == []
    assert client.delete(f"/owner/practices/{pid}/team/{tid}", headers=h).status_code == 404
    # a removed therapist cannot link themselves back without a new invitation
    r = client.post("/therapists/me/profile", headers=world["h"]["invitee"], json={"practice_id": pid, "fee": 1000, "bio": "", "approaches": [], "languages": ["en"]})
    assert r.status_code == 409


def test_removed_therapist_is_unlisted_but_keeps_their_care(world) -> None:
    pid = _ready(world)
    _verify(world, pid)
    client.post(f"/owner/practices/{pid}/publish", headers=world["h"]["owner"])
    _, token = _invite(world, pid, world["emails"]["invitee"])
    tid = client.post("/invitations/accept", headers=world["h"]["invitee"], json={"token": token}).json()["therapist_id"]
    with SessionLocal() as db:
        db.get(TherapistProfile, tid).verified = True
        db.commit()
    assert tid in [t["id"] for t in client.get("/therapists/public").json()["items"]]
    client.delete(f"/owner/practices/{pid}/team/{tid}", headers=world["h"]["owner"])
    assert tid not in [t["id"] for t in client.get("/therapists/public").json()["items"]]
    assert client.get("/therapists/me/profile", headers=world["h"]["invitee"]).status_code == 200  # their profile and clients remain


# ---------- seed ----------

def test_seed_adds_a_draft_practice_with_ai_draft_and_pending_invite(private_uploads) -> None:
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS])))
            db.execute(delete(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS + [seed_mod.SETUP_PRACTICE["slug"]])))
            db.commit()
    wipe()
    now = datetime(2030, 3, 4, 8, 0, tzinfo=timezone.utc)
    try:
        with SessionLocal() as db:
            seed_mod.seed(db, load_kb=False, now=now)
            seed_mod.seed(db, load_kb=False, now=now)  # idempotent
            practices = db.scalars(select(Practice).where(Practice.slug == seed_mod.SETUP_PRACTICE["slug"])).all()
            assert len(practices) == 1
            p = practices[0]
            assert (p.status, p.verification_status, p.verified) == ("draft", "draft", False)
            assert p.page_source == "ai" and p.page_text and not practice_setup.missing_details(p)
            assert db.scalar(select(func.count()).select_from(PracticeInvite).where(PracticeInvite.practice_id == p.id,
                                                                                   PracticeInvite.status == "pending")) == 1
            verified = db.scalars(select(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS))).all()
            assert len(verified) == 3 and all(v.verified and v.verification_status == "verified" and v.status == "published" for v in verified)
            owner = db.scalar(select(User).where(User.email == "owner4@example.com"))
            h = {"Authorization": f"Bearer {create_access_token(owner.email, owner.role)}"}
            pid = p.id
        setup = client.get(f"/owner/practices/{pid}/setup", headers=h).json()
        assert setup["missing"] == ["Documents: upload at least one document"] and len(setup["invites"]) == 1
        assert pid not in [x["id"] for x in client.get("/practices/public").json()["items"]]
        # the seeded invitation works for a therapist who signs up with that email
        email = seed_mod.SETUP_INVITE["email"]
        with SessionLocal() as db:
            db.add(User(email=email, password_hash=hash_password("x" * 12), role="therapist", name="New Therapist"))
            db.commit()
        th = {"Authorization": f"Bearer {create_access_token(email, 'therapist')}"}
        assert client.post("/invitations/accept", headers=th, json={"token": seed_mod.SETUP_INVITE["token"]}).status_code == 200
    finally:
        wipe()
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email == seed_mod.SETUP_INVITE["email"]))
            db.commit()
