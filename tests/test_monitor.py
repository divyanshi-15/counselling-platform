from __future__ import annotations

import json
import smtplib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app.agents import monitor
from backend.app.auth import create_access_token
from backend.app.clinical import raise_risk_alert, scan_client_text
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import (AgentRun, Alert, Assessment, Booking, CasePlan, PendingAction, Practice, TherapySession,
                                User)
from backend.scripts import seed as seed_mod

client = TestClient(app)
DRAFT = {"update_text": "Scores have held steady, so consider whether the evening goals and exercises still fit."}


def _wipe() -> None:
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS])))
        db.execute(delete(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS)))
        db.commit()


@pytest.fixture
def seeded():
    _wipe()
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False)
    yield
    _wipe()


@pytest.fixture
def model(monkeypatch):
    calls = []

    def fake(system, blocks, *, max_tokens):
        assert max_tokens > 0 and "Never diagnose" in system
        calls.append(blocks)
        return json.dumps(DRAFT)

    monkeypatch.setattr(monitor, "call_model", fake)
    return calls


def _user(email: str) -> User:
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.email == email))


def _h(email: str) -> dict[str, str]:
    u = _user(email)
    return {"Authorization": f"Bearer {create_access_token(u.email, u.role)}"}


def _run(email: str = "therapist@example.com") -> dict:
    r = client.post("/therapist/overnight-check", headers=_h(email))
    assert r.status_code == 200, r.text
    return r.json()


def _alpha_id() -> int:
    return _user("client@example.com").id


def _alerts(client_email: str, types: tuple[str, ...] = ("plateau", "homework", "goal_untouched")) -> list[Alert]:
    with SessionLocal() as db:
        return list(db.scalars(select(Alert).where(Alert.client_id == _user(client_email).id, Alert.type.in_(types))))


def _plan_actions(db=None) -> list[PendingAction]:
    with SessionLocal() as s:
        return list(s.scalars(select(PendingAction).where(PendingAction.type == "apply_plan_update")))


def test_plateau_detected_on_seeded_series(seeded, model):
    out = _run()
    assert out["drafted"] >= 1  # totals depend on other seeded clients; the assertions below are about Alpha
    types = {a.type for a in _alerts("client@example.com")}
    assert types == {"plateau", "homework", "goal_untouched"}
    plateau = next(a for a in _alerts("client@example.com") if a.type == "plateau")
    assert {d["measure"] for d in plateau.payload["detail"]} == {"PHQ9", "GAD7"}
    [action] = [a for a in _plan_actions() if a.payload.get("client_id") == _alpha_id()]
    assert action.status == "pending" and action.payload["update_text"] == DRAFT["update_text"]
    assert action.payload["ai_status"] == "ok" and action.assignee_user_id == _user("therapist@example.com").id
    with SessionLocal() as db:
        run = db.scalars(select(AgentRun).where(AgentRun.run_id == out["run_id"], AgentRun.tool == "summary")).one()
        assert run.agent == "monitor" and run.summary == out["summary"]
    assert len(model) == out["drafted"]  # one drafting call per draft; detection never touched the model


def test_improving_series_makes_no_alert(seeded, model):
    out = _run("therapist2@example.com")
    assert out["drafted"] == 0 and model == []
    assert _alerts("client3@example.com") == []
    assert not [a for a in _plan_actions() if a.payload.get("client_id") == _user("client3@example.com").id]
    assert _alerts("client2@example.com") == []  # improving client of therapist one


def test_homework_under_half_flagged(seeded):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        t1 = _user("therapist@example.com").id
        low = monitor.detect_low_homework(db, t1, _alpha_id(), now)
        assert low == {"assigned": 4, "completed": 1, "rate": 0.25}
        assert monitor.detect_low_homework(db, t1, _user("client2@example.com").id, now) is None


def test_rerun_creates_no_duplicates(seeded, model):
    _run()
    first = (len(_alerts("client@example.com")), len(_plan_actions()))
    again = _run()
    assert again["drafted"] == 0 and (len(_alerts("client@example.com")), len(_plan_actions())) == first
    # a later night while the draft still awaits approval adds no second draft either
    with SessionLocal() as db:
        monitor.run_overnight_check(db, _user("therapist@example.com"), now=datetime.now(timezone.utc) + timedelta(hours=20))
    assert len(_plan_actions()) == 1 and len(model) == 1


def test_nothing_applied_without_approval(seeded, model):
    _run()
    [action] = _plan_actions()
    url = f"/pending-actions/{action.id}/approve"
    t1 = _h("therapist@example.com")

    def versions():
        with SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(CasePlan).where(CasePlan.client_id == _alpha_id()))

    assert versions() == 1
    assert client.post(url, headers=t1).status_code == 409  # key required
    assert client.post(url, headers=t1 | {"Idempotency-Key": "wrong"}).status_code == 409
    assert versions() == 1
    ok = client.post(url, headers=t1 | {"Idempotency-Key": action.idempotency_key})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    assert client.post(url, headers=t1 | {"Idempotency-Key": action.idempotency_key}).status_code == 200  # replay
    assert versions() == 2
    with SessionLocal() as db:
        new = db.scalars(select(CasePlan).where(CasePlan.client_id == _alpha_id()).order_by(CasePlan.version.desc())).first()
        assert new.version == 2 and new.approved_at is not None and new.update_notes == DRAFT["update_text"]
        assert DRAFT["update_text"] not in new.formulation_text and new.update_notes_approved_by == new.therapist_user_id
        assert new.therapist_user_id == _user("therapist@example.com").id


def test_reject_applies_nothing_and_stale_plan_is_refused(seeded, model):
    _run()
    [action] = _plan_actions()
    t1 = _h("therapist@example.com") | {"Idempotency-Key": action.idempotency_key}
    # therapist edits the plan meanwhile -> approving the old draft must fail
    r = client.post(f"/clients/{_alpha_id()}/case-plans", headers=_h("therapist@example.com"),
                    json={"approach": "CBT-I", "formulation_text": "Revised.", "goals": [{"id": "g1", "text": "Sleep"}]})
    assert r.status_code == 200
    assert client.post(f"/pending-actions/{action.id}/approve", headers=t1).status_code == 409
    assert client.post(f"/pending-actions/{action.id}/reject", headers=t1).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CasePlan).where(CasePlan.client_id == _alpha_id())) == 2


def test_owner_client_and_other_therapist_denied(seeded, model):
    for email in ("owner@example.com", "client@example.com", "admin@example.com"):
        assert client.post("/therapist/overnight-check", headers=_h(email)).status_code == 403
    assert client.post("/therapist/overnight-check").status_code in (401, 403)
    _run()
    [action] = _plan_actions()
    url, key = f"/pending-actions/{action.id}", {"Idempotency-Key": action.idempotency_key}
    for email in ("owner@example.com", "therapist2@example.com", "client@example.com"):
        for verb in ("approve", "reject"):
            assert client.post(f"{url}/{verb}", headers=_h(email) | key).status_code == 403
    assert all(i["type"] != "apply_plan_update" for i in
               client.get("/pending-actions", headers=_h("owner@example.com")).json()["items"])
    items = client.get("/therapists/me/pending-actions", headers=_h("therapist2@example.com")).json()["items"]
    assert [i for i in items if i["status"] == "pending"] == []  # nothing of therapist one's is visible
    assert client.get("/therapists/me/alerts", headers=_h("therapist2@example.com")).json()["items"] == []
    # therapist two's own run never touches therapist one's client
    _run("therapist2@example.com")
    assert len(_plan_actions()) == 1
    owner_runs = client.get("/therapists/me/agent-runs", headers=_h("owner@example.com"))
    assert owner_runs.status_code == 403
    with SessionLocal() as db:
        assert _plan_actions()[0].status == "pending"


def test_seed_twice_is_safe(seeded):
    def counts():
        with SessionLocal() as db:
            return [db.scalar(select(func.count()).select_from(m).where(User.email.in_(["x"]) if m is User else True))
                    for m in (User, Booking, Assessment, CasePlan, TherapySession, Practice)] + \
                   [db.scalar(select(func.count()).select_from(User).where(User.email.like("%@example.com")))]

    before = counts()
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False)
    assert counts() == before


def test_seed_text_is_clean_and_shaped(seeded):
    banned = ("dying to", "killing me")
    with SessionLocal() as db:
        ids = db.scalars(select(User.id).where(User.email.in_([r[0] for r in seed_mod.LOGINS]))).all()
        texts = [s.raw_notes for s in db.scalars(select(TherapySession).where(TherapySession.client_id.in_(ids)))]
    for case in filter(None, seed_mod.CASES.values()):
        texts += [n for _, n in case["notes"]] + list(case["intake"].values()) + [g["text"] for g in case["goals"]]
        texts.append(case["formulation"])
    for text in texts:
        assert scan_client_text(text) is None, text
        assert not any(b in text.lower() for b in banned)
    with SessionLocal() as db:
        phq = db.scalars(select(Assessment).where(Assessment.client_id == _alpha_id(), Assessment.type == "PHQ9")).all()
        assert all(r.item_scores[8] == 0 and sum(r.item_scores) == r.total for r in phq)
        pub = db.scalars(select(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS))).all()
        assert sorted((p.status, p.verified) for p in pub) == [("published", True)] * 3


def test_risk_alert_sends_no_email(seeded, model, monkeypatch):
    smtp = MagicMock(side_effect=AssertionError("SMTP must not be used"))
    monkeypatch.setattr(smtplib, "SMTP", smtp)
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    with SessionLocal() as db:
        raise_risk_alert(db, therapist_user_id=_user("therapist@example.com").id, client_id=_alpha_id(),
                         source="checkin", source_id=1, match="test")
        db.commit()
    _run()
    smtp.assert_not_called()
    assert any(a.type == "risk" and a.priority == "high" for a in
               [x for x in _alerts("client@example.com", ("risk",))])


def test_ai_down_or_bad_output_still_drafts_manual_text(seeded, monkeypatch):
    monkeypatch.setattr(monitor, "call_model", lambda *a, **k: None)
    _run()
    [action] = _plan_actions()
    assert action.payload["ai_status"] == "manual" and "please edit" in action.payload["update_text"]
    # rerun with garbage output twice: visible error status, manual text, still only a draft
    with SessionLocal() as db:
        db.execute(delete(PendingAction).where(PendingAction.type == "apply_plan_update"))
        db.commit()
    bad = iter(["not json", json.dumps({"update_text": "This looks like depression; consider sertraline."})])
    monkeypatch.setattr(monitor, "call_model", lambda *a, **k: next(bad))
    _run()
    [action] = _plan_actions()
    assert action.payload["ai_status"].startswith("error") and "sertraline" not in action.payload["update_text"]


def test_risk_flagged_client_never_reaches_model(seeded, model):
    with SessionLocal() as db:
        s = db.scalars(select(TherapySession).where(TherapySession.client_id == _alpha_id())).first()
        s.risk_flag = True
        db.commit()
    _run()
    assert model == []
    [action] = _plan_actions()
    assert action.payload["ai_status"] == "manual"
