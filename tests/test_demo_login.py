from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import User
from backend.scripts import seed as seed_mod

client = TestClient(app)


@pytest.fixture()
def seeded():
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False)
    yield


def test_demo_login_disabled_by_default(seeded, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert client.get("/config").json()["demo_mode"] is False
    assert client.post("/auth/demo-login", params={"role": "client"}).status_code == 404


def test_demo_login_sets_cookie_and_only_known_roles(seeded, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    c = TestClient(app)
    r = c.post("/auth/demo-login", params={"role": "therapist"})
    assert r.status_code == 200
    assert c.get("/auth/me").json()["email"] == "therapist@example.com"
    assert c.post("/auth/demo-login", params={"role": "superuser"}).status_code == 404
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401
