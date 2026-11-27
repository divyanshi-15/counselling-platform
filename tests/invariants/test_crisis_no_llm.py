"""Invariant: the crisis path uses no LLM. Every client free-text sink, and PHQ-9 item 9 > 0, must return the fixed
Tele-MANAS 14416 message and raise a high-priority alert while every outbound HTTP call is forbidden and an API key
is present (so a model call would otherwise be attempted)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Alert, Assignment, AvailabilitySlot, Booking, IntakeForm, IntakeResponse, TherapistProfile

PHRASES = ["I want to end my life", "main marna chahta hoon", "मैं मरना चाहता हूँ"]


@pytest.fixture(autouse=True)
def no_outbound(monkeypatch):
    """Fail loudly if anything on the crisis path tries to leave the process."""
    import httpx
    import requests

    def boom(*args, **kwargs):
        raise AssertionError("outbound HTTP call on the crisis path")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("FAKE_LLM", raising=False)
    for name in ("post", "get", "put", "request", "stream"):
        monkeypatch.setattr(httpx, name, boom)
        if hasattr(requests, name):
            monkeypatch.setattr(requests, name, boom)
    monkeypatch.setattr(requests.Session, "request", boom)


@pytest.fixture(scope="module")
def web():
    with TestClient(app) as c:
        yield c


def _key() -> dict[str, str]:
    return {"Idempotency-Key": uuid4().hex}


def _alpha_booking(ids) -> Booking:
    with SessionLocal() as db:
        b = db.scalars(select(Booking).where(Booking.client_id == ids["client"]).order_by(Booking.id)).first()
        assert b is not None, "seed must give client Alpha a booking"
        return b


def _high_alerts(client_id: int) -> int:
    with SessionLocal() as db:
        return len(db.scalars(select(Alert).where(Alert.client_id == client_id, Alert.priority == "high")).all())


def _checkin(web, tokens, ids, text):
    with SessionLocal() as db:
        a = db.scalars(select(Assignment).where(Assignment.client_id == ids["client"], Assignment.status == "assigned")).first()
        assert a is not None, "seed must give client Alpha an open assignment"
    return web.post(f"/client/assignments/{a.id}/checkin", headers=tokens["client"],
                    json={"responses": {"situation": "bad day", "thought": text, "feeling_before": 9}})


def _intake(web, tokens, ids, text):
    b = _alpha_booking(ids)
    with SessionLocal() as db:
        profile = db.get(TherapistProfile, db.get(AvailabilitySlot, b.availability_slot_id).therapist_id)
        form = db.scalar(select(IntakeForm).where(IntakeForm.therapist_id == profile.id))
        db.execute(delete(IntakeResponse).where(IntakeResponse.booking_id == b.id))
        db.commit()
        answers = {f["id"]: ("Yes" if f.get("type") != "text" else "ok") for f in form.fields_json if f.get("required")}
        text_field = next(f["id"] for f in form.fields_json if f.get("type") in ("text", "textarea", None))
        answers[text_field] = text
    return web.post(f"/bookings/{b.id}/intake-response", headers=tokens["client"], json={"answers": answers})


SINKS = {
    "brain_dump": lambda w, t, i, x: w.post("/client/brain-dump", headers=t["client"] | _key(), json={"text": x}),
    "journal": lambda w, t, i, x: w.post("/client/journal", headers=t["client"] | _key(), json={"text": x, "shared": True}),
    "mood_note": lambda w, t, i, x: w.put("/client/mood", headers=t["client"], json={"mood": 1, "sleep_hours": 3, "note": x}),
    "exercise_checkin": _checkin,
    "intake_response": _intake,
}


@pytest.mark.parametrize("phrase", PHRASES)
@pytest.mark.parametrize("sink", list(SINKS))
def test_client_text_gets_fixed_message_and_alert(sink, phrase, web, tokens, ids) -> None:
    before = _high_alerts(ids["client"])
    resp = SINKS[sink](web, tokens, ids, phrase)
    assert resp.status_code == 200, resp.text
    assert "14416" in resp.text
    assert _high_alerts(ids["client"]) == before + 1


@pytest.mark.parametrize("phrase", PHRASES)
def test_session_transcript_gets_fixed_message_and_alert(phrase, web, tokens, ids) -> None:
    b = _alpha_booking(ids)
    before = _high_alerts(ids["client"])
    resp = web.put(f"/bookings/{b.id}/session-notes", headers=tokens["therapist"], json={"raw_notes": f"Client said: {phrase}", "source": "transcript"})
    assert resp.status_code == 200, resp.text
    assert "14416" in resp.text
    assert _high_alerts(ids["client"]) == before + 1


@pytest.mark.parametrize("path,extra", [("/contact", {}), ("/practices/contact", {"practice": "P"})])
def test_public_contact_forms_return_fixed_message(path, extra, web) -> None:
    resp = web.post(path, headers=_key(), json={"name": "A", "email": "a@example.com", "message": PHRASES[0]} | extra)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "crisis" and "14416" in resp.json()["message"]


def test_phq9_item9_positive_raises_high_priority_alert(web, tokens, ids) -> None:
    before = _high_alerts(ids["client"])
    resp = web.post(f"/clients/{ids['client']}/assessments", headers=tokens["therapist"],
                    json={"type": "PHQ9", "item_scores": [0, 0, 0, 0, 0, 0, 0, 0, 1]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["risk_alert"] is True
    assert _high_alerts(ids["client"]) == before + 1


def test_outbound_guard_actually_blocks() -> None:
    import httpx

    with pytest.raises(AssertionError):
        httpx.post("https://api.anthropic.com/v1/messages")
