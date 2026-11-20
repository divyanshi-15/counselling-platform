from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app.auth import create_access_token, hash_password
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import AuditLog, TherapistProfile, User
from backend.app.verification import backfill_draft_profiles

client = TestClient(app)
PW = "x" * 12


@pytest.fixture
def cleanup():
    emails: list[str] = []
    yield emails
    with SessionLocal() as db:
        ids = [u for (u,) in db.execute(select(User.id).where(User.email.in_(emails)))]
        db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()


def _profile(email: str) -> list[TherapistProfile]:
    with SessionLocal() as db:
        return list(db.scalars(select(TherapistProfile).join(User, User.id == TherapistProfile.user_id).where(User.email == email)))


def _headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(email, 'therapist')}"}


def _bare_therapist(cleanup) -> str:
    email = f"bare-{uuid4().hex[:8]}@example.com"
    cleanup.append(email)
    with SessionLocal() as db:
        db.add(User(email=email, password_hash=hash_password(PW), role="therapist", name="Bare"))
        db.commit()
    return email


def test_signup_creates_draft_profile(cleanup) -> None:
    email = f"new-{uuid4().hex[:8]}@example.com"
    cleanup.append(email)
    r = client.post("/auth/register", json={"email": email, "password": PW, "role": "therapist", "name": "New Therapist"})
    assert r.status_code == 200, r.text
    (p,) = _profile(email)
    assert (p.verification_status, p.practice_id, p.verified) == ("draft", None, False)
    me = client.get("/therapists/me/profile", headers=_headers(email)).json()
    assert me["practice_id"] is None and me["verification_status"] == "draft" and me["verified"] is False
    assert all(t["id"] != p.id for t in client.get("/therapists/public").json()["items"])


def test_client_signup_creates_no_profile(cleanup) -> None:
    email = f"cl-{uuid4().hex[:8]}@example.com"
    cleanup.append(email)
    assert client.post("/auth/register", json={"email": email, "password": PW, "role": "client", "name": "C"}).status_code == 200
    assert _profile(email) == []


def test_profile_and_verification_endpoints_create_draft_lazily(cleanup) -> None:
    email = _bare_therapist(cleanup)
    assert _profile(email) == []
    r = client.get("/therapists/me/verification", headers=_headers(email))
    assert r.status_code == 200 and r.json()["status"] == "draft"
    assert set(r.json()["missing"]) == {"education", "license", "document"}
    assert len(_profile(email)) == 1
    assert client.get("/therapists/me/profile", headers=_headers(email)).status_code == 200
    assert len(_profile(email)) == 1


def test_lazy_creation_via_profile_get_and_patch(cleanup) -> None:
    email = _bare_therapist(cleanup)
    assert client.get("/therapists/me/profile", headers=_headers(email)).json()["verification_status"] == "draft"
    other = _bare_therapist(cleanup)
    r = client.patch("/therapists/me/profile", headers=_headers(other), json={"bio": "Hello", "fee": 900})
    assert r.status_code == 200 and r.json()["practice_id"] is None


def test_backfill_is_idempotent(cleanup) -> None:
    emails = [_bare_therapist(cleanup) for _ in range(2)]
    with SessionLocal() as db:
        assert backfill_draft_profiles(db) >= 2
    with SessionLocal() as db:
        assert backfill_draft_profiles(db) == 0
        n = db.scalar(select(func.count()).select_from(TherapistProfile).join(User, User.id == TherapistProfile.user_id)
                      .where(User.email.in_(emails)))
    assert n == 2


def test_therapist_cannot_set_a_practice(cleanup) -> None:
    email = _bare_therapist(cleanup)
    h = _headers(email)
    for body in ({"practice_id": 1}, {"verified": True}):
        assert client.patch("/therapists/me/profile", headers=h, json=body).status_code == 422
    r = client.post("/therapists/me/profile", headers=h, json={"bio": "b", "approaches": ["CBT"], "languages": ["en"], "fee": 1000, "practice_id": 1})
    assert r.status_code == 422
    r = client.post("/therapists/me/profile", headers=h, json={"bio": "b", "approaches": ["CBT"], "languages": ["en"], "fee": 1000})
    assert r.status_code == 200 and r.json()["practice_id"] is None
    assert _profile(email)[0].practice_id is None


def test_banner_state_comes_from_api(cleanup) -> None:
    email = _bare_therapist(cleanup)
    h = _headers(email)
    v = client.get("/therapists/me/verification", headers=h).json()
    assert v["status"] == "draft" and v["reviewer_note"] is None and v["can_edit_documents"] is True
    with SessionLocal() as db:
        p = db.scalars(select(TherapistProfile).join(User, User.id == TherapistProfile.user_id).where(User.email == email)).one()
        p.verification_status, p.reviewer_note = "changes_requested", "Upload a clearer licence scan"
        db.commit()
    v = client.get("/therapists/me/verification", headers=h).json()
    assert (v["status"], v["reviewer_note"]) == ("changes_requested", "Upload a clearer licence scan")
    assert client.get("/therapists/me/profile", headers=h).json()["verification_status"] == "changes_requested"
