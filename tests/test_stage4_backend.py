from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.app import fake_llm
from backend.app.agents import copilot, launch, monitor
from backend.app.auth import create_access_token
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Alert, AuditLog, CasePlan, PendingAction, Practice, User
from backend.scripts import seed as seed_mod

client = TestClient(app)


@pytest.fixture
def seeded():
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS])))
            db.execute(delete(Practice).where(Practice.slug.in_(["demo-calm-minds", "demo-harbour-counselling"])))
            db.commit()
    wipe()
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False)
    yield
    wipe()


def _h(email: str) -> dict[str, str]:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        return {"Authorization": f"Bearer {create_access_token(u.email, u.role)}"}


def _overnight(monkeypatch) -> None:
    monkeypatch.setattr(monitor, "call_model", lambda *a, **k: json.dumps({"update_text": "Consider whether the goals still fit."}))
    assert client.post("/therapist/overnight-check", headers=_h("therapist@example.com")).status_code == 200


def _alert_id() -> int:
    with SessionLocal() as db:
        return db.scalars(select(Alert).where(Alert.type == "plateau")).first().id


def test_acknowledge_alert_idempotent_and_audited(seeded, monkeypatch):
    _overnight(monkeypatch)
    aid = _alert_id()
    h = _h("therapist@example.com")
    first = client.post(f"/alerts/{aid}/acknowledge", headers=h)
    assert first.status_code == 200 and first.json()["acknowledged"] and first.json()["acknowledged_at"]
    again = client.post(f"/alerts/{aid}/acknowledge", headers=h)
    assert again.status_code == 200 and again.json()["acknowledged_at"] == first.json()["acknowledged_at"]
    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.action == "alert.acknowledge", AuditLog.entity_id == aid)).all()
        assert [r.details["idempotent_replay"] for r in rows] == [False, True]
        assert all(r.actor_id == db.scalar(select(User.id).where(User.email == "therapist@example.com")) for r in rows)


@pytest.mark.parametrize("who", ["therapist2@example.com", "owner@example.com", "client@example.com", "admin@example.com", None])
def test_acknowledge_alert_denied(seeded, monkeypatch, who):
    _overnight(monkeypatch)
    aid = _alert_id()
    r = client.post(f"/alerts/{aid}/acknowledge", headers=_h(who) if who else {})
    assert r.status_code == (401 if who is None else 403)
    with SessionLocal() as db:
        a = db.get(Alert, aid)
        assert not a.acknowledged and a.acknowledged_at is None
        assert db.scalars(select(AuditLog).where(AuditLog.action == "alert.acknowledge", AuditLog.entity_id == aid)).first() is None


def test_acknowledge_missing_alert_404(seeded):
    assert client.post("/alerts/999999/acknowledge", headers=_h("therapist@example.com")).status_code == 404


def test_plan_update_preview_has_diff_matching_apply(seeded, monkeypatch):
    _overnight(monkeypatch)
    h = _h("therapist@example.com")
    [item] = [i for i in client.get("/therapists/me/pending-actions", headers=h).json()["items"] if i["type"] == "apply_plan_update"]
    d = item["diff"]
    assert d["stale"] is False and d["changed"] == ["formulation"]
    assert d["before"]["approach"] == d["after"]["approach"] == "CBT-I"
    assert d["before"]["goals"] == d["after"]["goals"] == ["Reduce racing thoughts at bedtime", "Reconnect with weekend football friends"]
    assert "Consider whether the goals still fit." in d["after"]["formulation"]
    r = client.post(f"/pending-actions/{item['id']}/approve", headers=h | {"Idempotency-Key": item["idempotency_key"]})
    assert r.status_code == 200
    with SessionLocal() as db:
        newest = db.scalars(select(CasePlan).where(CasePlan.client_id == item["payload"]["client_id"]).order_by(CasePlan.version.desc())).first()
        assert newest.version == 2 and newest.formulation_text.split("approved by therapist): ")[1] == "Consider whether the goals still fit."
    assert d["after"]["formulation"].split("\n\n")[0] == newest.formulation_text.split("\n\n")[0]
    other = client.get("/therapists/me/pending-actions", headers=_h("therapist2@example.com")).json()["items"]
    assert not any(i["type"] == "apply_plan_update" for i in other)


def test_non_plan_actions_have_no_diff(seeded, monkeypatch):
    monkeypatch.setattr(copilot, "call_model", lambda *a, **k: None)
    client.post("/therapists/me/prepare-my-day", headers=_h("therapist@example.com"))
    items = client.get("/therapists/me/pending-actions", headers=_h("therapist@example.com")).json()["items"]
    assert items and all(i["diff"] is None for i in items)


# ---------- FAKE_LLM ----------

def test_fake_llm_guard(monkeypatch):
    monkeypatch.setenv("FAKE_LLM", "1")
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(fake_llm.FakeLLMConfigError):
        fake_llm.assert_safe_config()
    with pytest.raises(fake_llm.FakeLLMConfigError):
        with TestClient(app):  # lifespan = real startup path
            pass
    for env, demo, fake in [("production", "1", "1"), ("development", "0", "1"), ("production", "0", "0")]:
        monkeypatch.setenv("APP_ENV", env); monkeypatch.setenv("DEMO_MODE", demo); monkeypatch.setenv("FAKE_LLM", fake)
        fake_llm.assert_safe_config()
    monkeypatch.setenv("FAKE_LLM", "1"); monkeypatch.setenv("DEMO_MODE", "1"); monkeypatch.setenv("APP_ENV", "production")
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_fake_llm_outputs_are_deterministic_and_never_call_network(monkeypatch):
    monkeypatch.setenv("FAKE_LLM", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("httpx.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network call")))
    page = launch.run_launch_agent({"name": "Demo Quiet Practice", "location": "Pune"})
    assert page["page"]["tagline"] == launch.run_launch_agent({"name": "Demo Quiet Practice", "location": "Pune"})["page"]["tagline"]
    assert "Pune" in page["page"]["tagline"] and "Demo Quiet Practice" in page["page"]["about"]
    blocks = [("RETRIEVED knowledge entries (cite only these chunk_ids):\n" + json.dumps([{"chunk_id": 7, "title": "t", "text": "x"}]), True),
              ("Case context:\n{}", False)]
    out = json.loads(copilot.call_model(copilot.SYSTEM_PROMPT, blocks, max_tokens=100))
    assert out["suggestions"][0]["chunk_ids"] == [7]
    assert copilot.call_model(copilot.SYSTEM_PROMPT, [("Structure these session notes. x", False)], max_tokens=10)
    assert json.loads(copilot.call_model(monitor.SYSTEM_PROMPT, [("x", False)], max_tokens=10))["update_text"]
