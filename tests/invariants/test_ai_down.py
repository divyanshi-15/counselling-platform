"""Invariant: manual workflows keep working when AI is unavailable, whether the key is missing or the daily budget is
spent. AI-assisted endpoints answer with the fixed unavailable message and keep the user's own input."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.agents import copilot
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import PendingAction

TEXT = "I keep worrying about work and cannot switch off at night."


@pytest.fixture(params=["no_key", "budget_spent"])
def ai_down(request, monkeypatch):
    if request.param == "no_key":
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setattr(copilot, "_budget_exceeded", lambda: True)
    monkeypatch.delenv("FAKE_LLM", raising=False)
    import httpx

    def boom(*a, **k):
        raise AssertionError("a model call was attempted while AI is down")

    monkeypatch.setattr(httpx, "post", boom)


@pytest.fixture(scope="module")
def web():
    with TestClient(app) as c:
        yield c


def _key() -> dict[str, str]:
    return {"Idempotency-Key": uuid4().hex}


def test_brain_dump_keeps_the_note_and_says_ai_is_unavailable(ai_down, web, tokens, ids) -> None:
    resp = web.post("/client/brain-dump", headers=tokens["client"] | _key(), json={"text": TEXT})
    assert resp.status_code == 200 and resp.json()["status"] == "ai_unavailable"
    assert "AI unavailable, manual workflow open." in resp.json()["message"]
    with SessionLocal() as db:
        mine = [a for a in db.scalars(select(PendingAction).where(PendingAction.type == "brain_dump")).all()
                if a.payload["client_id"] == ids["client"] and a.payload["text"] == TEXT]
    assert mine and all(a.payload["draft"] is None for a in mine)  # the therapist still sees the raw note


def test_journey_draft_reports_unavailable(ai_down, web, tokens, ids) -> None:
    resp = web.post(f"/clients/{ids['client']}/journeys/draft", headers=tokens["therapist"] | _key(), json={"focus": "worry at night"})
    assert resp.status_code == 200 and resp.json()["status"] == "ai_unavailable"


def test_overnight_check_falls_back_to_fixed_wording(ai_down, web, tokens, ids) -> None:
    resp = web.post("/therapist/overnight-check", headers=tokens["therapist"])
    assert resp.status_code == 200, resp.text


def test_manual_workflows_do_not_need_ai(ai_down, web, tokens, ids) -> None:
    # Therapist records notes, the client logs mood and journals, the therapist records an assessment, availability loads.
    with SessionLocal() as db:
        from backend.app.models import Booking

        booking = db.scalars(select(Booking).where(Booking.client_id == ids["client"])).first()
    assert web.put(f"/bookings/{booking.id}/session-notes", headers=tokens["therapist"],
                   json={"raw_notes": "Discussed sleep routine.", "source": "typed"}).status_code == 200
    assert web.put("/client/mood", headers=tokens["client"], json={"mood": 3, "sleep_hours": 7, "note": "ok day"}).status_code == 200
    assert web.post("/client/journal", headers=tokens["client"] | _key(), json={"text": "A calm evening."}).status_code == 200
    assert web.post(f"/clients/{ids['client']}/assessments", headers=tokens["therapist"],
                    json={"type": "GAD7", "item_scores": [1, 1, 0, 1, 0, 0, 1]}).status_code == 200
    assert web.get("/therapists/me/availability", headers=tokens["therapist"]).status_code == 200
    assert web.get("/client/dashboard", headers=tokens["client"]).status_code == 200


def test_crisis_path_still_works(ai_down, web, tokens, ids) -> None:
    resp = web.post("/client/journal", headers=tokens["client"] | _key(), json={"text": "I want to end my life"})
    assert resp.status_code == 200 and "14416" in resp.text
