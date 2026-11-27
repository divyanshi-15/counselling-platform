"""Invariants: AI only proposes, and its output passes the deterministic post-check before anyone sees it.
Runs the real endpoints with a stubbed model: benign output must land as a pending action with nothing applied;
hostile output (diagnosis and medication advice) must never be stored or surfaced."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.agents import copilot, monitor
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Assignment, CasePlan, Journey, JourneyAssignment, PendingAction

HOSTILE = "You have major depressive disorder. Take 5 mg melatonin each night."
TEXT = "I keep worrying about work and cannot switch off at night."


@pytest.fixture(scope="module")
def web():
    with TestClient(app) as c:
        yield c


def _key() -> dict[str, str]:
    return {"Idempotency-Key": uuid4().hex}


def _count(model, *where) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where))


def _model(monkeypatch, payload) -> list:
    calls: list = []

    def fake(system, blocks, *, max_tokens):
        calls.append(blocks)
        return json.dumps(payload)

    monkeypatch.setattr(copilot, "call_model", fake)
    monkeypatch.setattr(monitor, "call_model", fake)
    return calls


def _pending(action_type: str, **payload_match) -> list[PendingAction]:
    with SessionLocal() as db:
        rows = db.scalars(select(PendingAction).where(PendingAction.type == action_type)).all()
    return [r for r in rows if all(r.payload.get(k) == v for k, v in payload_match.items())]


def test_brain_dump_output_is_a_pending_draft_and_applies_nothing(web, tokens, ids, monkeypatch) -> None:
    good = {"themes": ["work worry", "poor sleep"], "mood_tags": ["anxious"], "exercise_kb_slug": None,
            "summary": "The client describes work worry that follows them into the night. A calming routine may help."}
    _model(monkeypatch, good)
    assignments = _count(Assignment, Assignment.client_id == ids["client"])
    resp = web.post("/client/brain-dump", headers=tokens["client"] | _key(), json={"text": TEXT})
    assert resp.status_code == 200 and resp.json()["status"] == "shared"
    (action,) = _pending("brain_dump", client_id=ids["client"])
    assert action.status == "pending" and action.payload["draft"]["themes"] == good["themes"]
    assert _count(Assignment, Assignment.client_id == ids["client"]) == assignments  # nothing applied


def test_approval_needs_an_idempotency_key_and_replays_safely(web, tokens, ids) -> None:
    (action,) = _pending("brain_dump", client_id=ids["client"])
    url = f"/pending-actions/{action.id}/approve"
    assert web.post(url, headers=tokens["therapist"]).status_code in (409, 422)  # no Idempotency-Key: refused
    assert _pending("brain_dump", client_id=ids["client"])[0].status == "pending"
    headers = tokens["therapist"] | {"Idempotency-Key": action.idempotency_key}
    first = web.post(url, headers=headers)
    assignments = _count(Assignment, Assignment.client_id == ids["client"])
    second = web.post(url, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert _count(Assignment, Assignment.client_id == ids["client"]) == assignments  # replay applied nothing twice


def test_brain_dump_rejects_hostile_model_output(web, tokens, ids, monkeypatch) -> None:
    calls = _model(monkeypatch, {"themes": [HOSTILE], "mood_tags": ["low"], "exercise_kb_slug": None, "summary": HOSTILE})
    resp = web.post("/client/brain-dump", headers=tokens["client"] | _key(), json={"text": TEXT + " Again tonight."})
    assert resp.status_code == 200 and resp.json()["status"] == "error"
    assert len(calls) == 2  # one informed retry, then a visible error
    with SessionLocal() as db:
        stored = json.dumps([a.payload for a in db.scalars(select(PendingAction)).all()])
    assert "melatonin" not in stored and "depressive disorder" not in stored


def test_journey_draft_rejects_hostile_model_output(web, tokens, ids, monkeypatch) -> None:
    step = {"week": 1, "exercise": "worry-postponement", "text_en": HOSTILE, "text_hi": None}
    _model(monkeypatch, {"title_en": HOSTILE, "title_hi": None, "steps": [step]})
    journeys = _count(Journey)
    drafts = len(_pending("journey_draft"))
    resp = web.post(f"/clients/{ids['client']}/journeys/draft", headers=tokens["therapist"] | _key(), json={"focus": "worry at night"})
    assert resp.status_code == 200 and resp.json()["status"] == "error"
    assert len(_pending("journey_draft")) == drafts and _count(Journey) == journeys
    assert _count(JourneyAssignment, JourneyAssignment.client_id == ids["client"]) == 0


def test_overnight_check_uses_fixed_text_when_model_output_is_hostile(web, tokens, ids, monkeypatch) -> None:
    _model(monkeypatch, {"update_text": HOSTILE})
    plans = _count(CasePlan, CasePlan.client_id == ids["client"])
    resp = web.post("/therapist/overnight-check", headers=tokens["therapist"])
    assert resp.status_code == 200, resp.text
    actions = _pending("apply_plan_update", client_id=ids["client"])
    assert actions, "seed gives Alpha a plateau, so the check must propose a plan update"
    assert all(a.status == "pending" for a in actions)
    # The proposed wording is the fixed template. (ai_status still quotes the matched fragments for the therapist.)
    for a in actions:
        assert "melatonin" not in a.payload["update_text"] and "depressive" not in a.payload["update_text"]
        assert a.payload["ai_status"].startswith("error")
    assert _count(CasePlan, CasePlan.client_id == ids["client"]) == plans  # proposing never writes the plan
