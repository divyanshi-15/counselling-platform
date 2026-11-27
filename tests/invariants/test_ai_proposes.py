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
from backend.app.models import AgentRun, Assignment, CasePlan, CopilotBriefing, Journey, JourneyAssignment, PendingAction

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


HOSTILE_FRAGMENTS = ("melatonin", "depressive", "5 mg")


_BASELINE: dict[str, int] = {}


@pytest.fixture(scope="module", autouse=True)
def _baseline(seeded_world):
    """Other suites leave rows in the shared test database; only rows created from here on are inspected."""
    with SessionLocal() as db:
        for model in (PendingAction, AgentRun, CopilotBriefing):
            _BASELINE[model.__name__] = db.scalar(select(func.coalesce(func.max(model.id), 0)))


def _assert_no_hostile_text_stored() -> None:
    """Neither pending actions, agent-run logs nor briefings may contain fragments of rejected model output."""
    with SessionLocal() as db:
        stored = json.dumps([a.payload for a in db.scalars(select(PendingAction).where(PendingAction.id > _BASELINE["PendingAction"])).all()], default=str)
        stored += json.dumps([r.summary for r in db.scalars(select(AgentRun).where(AgentRun.id > _BASELINE["AgentRun"])).all()], default=str)
        stored += json.dumps([b.briefing_json for b in db.scalars(select(CopilotBriefing).where(CopilotBriefing.id > _BASELINE["CopilotBriefing"])).all()], default=str)
    for fragment in HOSTILE_FRAGMENTS:
        assert fragment not in stored.lower(), f"'{fragment}' from rejected model output was stored"


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
    assert web.post(url, headers=tokens["therapist"]).status_code == 422  # no Idempotency-Key
    wrong = web.post(url, headers=tokens["therapist"] | {"Idempotency-Key": "not-the-key"})
    assert wrong.status_code == 409
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
    _assert_no_hostile_text_stored()


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
    # The proposed wording is the fixed template, and nothing quoted from the rejected output is stored anywhere.
    for a in actions:
        assert a.payload["ai_status"].startswith("error")
    _assert_no_hostile_text_stored()
    assert _count(CasePlan, CasePlan.client_id == ids["client"]) == plans  # proposing never writes the plan


def test_copilot_briefing_rejects_hostile_model_output(web, tokens, monkeypatch) -> None:
    hostile_briefing = {"summary": HOSTILE, "suggestions": [{"text": HOSTILE}]}

    def fake(system, blocks, *, max_tokens):
        if "Structure these session notes" in blocks[0][0]:
            return json.dumps({"themes": ["sleep"], "client_reported": ["lies awake"], "homework": None})
        return json.dumps(hostile_briefing)

    monkeypatch.setattr(copilot, "call_model", fake)
    resp = web.post("/therapists/me/prepare-my-day", headers=tokens["therapist"])
    assert resp.status_code == 200, resp.text
    assert not any(f in resp.text.lower() for f in HOSTILE_FRAGMENTS)
    assert all(i.get("status") != "ok" for i in resp.json()["items"] if "status" in i)
    _assert_no_hostile_text_stored()


def test_practice_page_draft_rejects_hostile_model_output(monkeypatch) -> None:
    from fastapi import HTTPException

    from backend.app import practice_setup
    from backend.app.models import Practice

    page = {"tagline": HOSTILE, "about": HOSTILE, "services": [{"title": "Care", "description": HOSTILE}],
            "faq": [{"question": "q", "answer": HOSTILE}], "what_to_expect": [HOSTILE]}
    _model(monkeypatch, page)
    with SessionLocal() as db:
        practice = db.scalar(select(Practice).where(Practice.slug == "calm-minds-bengaluru"))
        assert practice is not None
        inputs = practice_setup._ai_inputs(practice)
    with pytest.raises(HTTPException) as err:
        practice_setup.propose_page(inputs)
    assert err.value.status_code == 502
    assert not any(f in str(err.value.detail).lower() for f in HOSTILE_FRAGMENTS)
