from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Practice, TherapistProfile, User
from backend.scripts import seed as seed_mod
from backend.scripts.create_admin import create_admin

client = TestClient(app)


def _reg(role: str = "client", **extra):
    email = f"{uuid4().hex[:10]}@example.com"
    r = TestClient(app).post("/auth/register", json={"email": email, "password": "password123", "role": role, **extra})
    return email, r


def _login(email: str) -> TestClient:
    c = TestClient(app)
    assert c.post("/auth/login", json={"email": email, "password": "password123"}).status_code == 200
    return c


@pytest.mark.parametrize("role", ["admin", "ADMIN", "superuser", "", None])
def test_register_rejects_admin_and_unknown_roles(role) -> None:
    email, r = _reg(role)
    assert r.status_code in (403, 422)
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == email).first() is None


@pytest.mark.parametrize("extra", [{"is_admin": True}, {"is_verified": True}, {"verified": True}, {"admin": True}])
def test_register_rejects_privileged_extra_fields(extra) -> None:
    email, r = _reg("client", **extra)
    assert r.status_code == 422
    email, r = _reg("admin", **extra)
    assert r.status_code in (403, 422)


@pytest.mark.parametrize("role", ["client", "therapist", "practice_owner"])
def test_self_registered_roles_start_unverified(role) -> None:
    email, r = _reg(role)
    assert r.status_code == 200 and r.json()["role"] == role
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == email).one().is_verified is False


def test_self_registered_therapist_is_not_public_and_cannot_self_verify() -> None:
    owner_email, _ = _reg("practice_owner")
    t_email, _ = _reg("therapist")
    with SessionLocal() as db:
        owner = db.query(User).filter(User.email == owner_email).one()
        practice = Practice(name="Pub", slug=uuid4().hex, owner_id=owner.id, status="published", verified=True)
        db.add(practice)
        db.commit()
        pid = practice.id
    t = _login(t_email)
    # a therapist without an accepted invitation has no profile and cannot create one, even for a verified practice
    assert t.post("/therapists/me/profile", json={"fee": 1000}).status_code == 403
    assert t.post("/therapists/me/profile", json={"practice_id": pid, "fee": 1000}).status_code == 422
    assert t.post("/therapists/me/profile", json={"fee": 1000, "verified": True}).status_code == 422
    with SessionLocal() as db:
        db.add(TherapistProfile(user_id=db.query(User).filter(User.email == t_email).one().id, practice_id=pid, fee=1000, verified=False))
        db.commit()
    r = t.post("/therapists/me/profile", json={"fee": 1000})
    assert r.status_code == 200 and r.json()["verified"] is False
    with SessionLocal() as db:
        profile = db.query(TherapistProfile).join(User, User.id == TherapistProfile.user_id).filter(User.email == t_email).one()
        tid = profile.id
        assert profile.verified is False
    assert tid not in [i["id"] for i in client.get("/therapists/public").json()["items"]]
    assert t.post(f"/admin/therapists/{tid}/review", json={"decision": "verified"}).status_code == 403
    assert _login(owner_email).post(f"/admin/practices/{pid}/review", json={"decision": "verified"}).status_code == 403


def test_unverified_practice_stays_invisible_and_owner_cannot_verify() -> None:
    email, _ = _reg("practice_owner")
    o = _login(email)
    r = o.post("/practices/draft", json={"name": "Calm Space", "location": "Pune", "verified": True})
    assert r.status_code == 422
    r = o.post("/practices/draft", json={"name": "Calm Space", "location": "Pune"})
    assert r.status_code == 200
    pid, action = r.json()["id"], r.json()["pending_action"]
    assert o.post(f"/pending-actions/{action['id']}/approve", headers={"Idempotency-Key": action["idempotency_key"]}).status_code == 200
    assert pid not in [i["id"] for i in client.get("/practices/public").json()["items"]]
    assert o.post(f"/admin/practices/{pid}/review", json={"decision": "verified"}).status_code == 403


def test_client_cannot_patch_or_escalate_own_role() -> None:
    email, _ = _reg("client")
    c = _login(email)
    for method in ("patch", "put", "post"):
        r = getattr(c, method)("/auth/me", json={"role": "admin"})
        assert r.status_code in (404, 405, 403)
    assert c.get("/auth/me").json()["role"] == "client"
    assert c.post("/practices/draft", json={"name": "X", "location": "Y"}).status_code == 403
    assert c.post("/admin/practices/1/review", json={"decision": "verified"}).status_code == 403


def test_demo_login_refuses_admin_and_404_when_off(monkeypatch) -> None:
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False)
    monkeypatch.setenv("DEMO_MODE", "1")
    c = TestClient(app)
    assert c.post("/auth/demo-login", params={"role": "admin"}).status_code == 404
    assert c.get("/auth/me").status_code == 401
    monkeypatch.setenv("DEMO_MODE", "0")
    for role in ("client", "therapist", "practice_owner", "admin"):
        assert c.post("/auth/demo-login", params={"role": role}).status_code == 404


def test_create_admin_cli_function_is_only_admin_path() -> None:
    email = f"{uuid4().hex[:8]}@example.com"
    with SessionLocal() as db:
        assert create_admin(db, email, "password123").role == "admin"
        with pytest.raises(ValueError):
            create_admin(db, email, "password123")
    assert TestClient(app).post("/auth/login", json={"email": email, "password": "password123"}).status_code == 200
