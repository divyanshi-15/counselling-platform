from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import (
    AvailabilitySlot,
    Booking,
    Practice,
    TherapistProfile,
    User,
)


def _register(client: TestClient, role: str) -> tuple[str, int]:
    email = f"{role}-{uuid4().hex}@example.com"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secret1234", "role": role, "language": "en", "name": role.title()},
    )
    assert response.status_code == 200, response.text
    login = client.post("/auth/login", json={"email": email, "password": "secret1234"})
    assert login.status_code == 200, login.text
    client_id = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['token']}"}).json()["id"]
    client.cookies.clear()
    return login.json()["token"], client_id


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_practice(owner_id: int, name: str, *, published: bool = True, verified: bool = True) -> Practice:
    with SessionLocal() as db:
        practice = Practice(
            name=name,
            slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:8]}",
            owner_id=owner_id,
            status="published" if published else "draft",
            verified=verified,
            page_json="{}",
        )
        db.add(practice)
        db.commit()
        db.refresh(practice)
        return practice


def _make_profile(user_id: int, practice_id: int, *, verified: bool = True) -> TherapistProfile:
    with SessionLocal() as db:
        profile = TherapistProfile(
            user_id=user_id,
            practice_id=practice_id,
            bio="Demo therapist",
            approaches=["CBT"],
            languages=["en"],
            fee=2000,
            verified=verified,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile


def _make_slot(therapist_id: int) -> AvailabilitySlot:
    with SessionLocal() as db:
        starts_at = datetime.now(timezone.utc) + timedelta(days=2)
        slot = AvailabilitySlot(therapist_id=therapist_id, starts_at=starts_at, ends_at=starts_at + timedelta(minutes=50))
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot


def test_therapist_booking_intake_dashboard_and_access_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "demo-user")
    monkeypatch.setenv("SMTP_PASS", "demo-pass")
    monkeypatch.setenv("SMTP_FROM", "demo@example.com")
    with TestClient(app) as client:
        client_token, client_id = _register(client, "client")
        other_client_token, _ = _register(client, "client")
        therapist_token, therapist_id = _register(client, "therapist")
        other_therapist_token, other_therapist_id = _register(client, "therapist")
        unverified_therapist_token, unverified_therapist_id = _register(client, "therapist")
        owner_token, owner_id = _register(client, "practice_owner")
        other_owner_token, other_owner_id = _register(client, "practice_owner")
        admin_token, _ = _register(client, "admin")

        practice = _make_practice(owner_id, "Practice One")
        other_practice = _make_practice(other_owner_id, "Practice Two")
        draft_practice = _make_practice(owner_id, "Draft Practice", published=False)
        unverified_practice = _make_practice(owner_id, "Unverified Practice", verified=False)
        therapist = _make_profile(therapist_id, practice.id)
        other_therapist = _make_profile(other_therapist_id, other_practice.id)
        unverified_therapist = _make_profile(unverified_therapist_id, practice.id, verified=False)
        slot = _make_slot(therapist.id)
        other_slot = _make_slot(other_therapist.id)

        therapist_headers = _headers(therapist_token)
        other_therapist_headers = _headers(other_therapist_token)
        client_headers = _headers(client_token)
        other_client_headers = _headers(other_client_token)
        owner_headers = _headers(owner_token)
        other_owner_headers = _headers(other_owner_token)
        admin_headers = _headers(admin_token)

        saved_profile = client.put(
            "/therapists/me/profile",
            json={"practice_id": practice.id, "bio": "Updated demo profile", "approaches": ["CBT"], "languages": ["en", "kn"], "fee": 2500},
            headers=therapist_headers,
        )
        assert saved_profile.status_code == 405
        created_profile = client.post(
            "/therapists/me/profile",
            json={"practice_id": practice.id, "bio": "Updated demo profile", "approaches": ["CBT"], "languages": ["en", "kn"], "fee": 2500},
            headers=therapist_headers,
        )
        assert created_profile.status_code == 200, created_profile.text
        therapist_profile = client.get("/therapists/me/profile", headers=therapist_headers)
        assert therapist_profile.status_code == 200
        assert therapist_profile.json()["id"] == therapist.id
        assert client.get("/therapists/me/profile", headers=owner_headers).status_code == 403
        assert client.post(
            "/therapists/me/profile",
            json={"practice_id": practice.id, "bio": "", "approaches": [], "languages": [], "fee": 1000},
            headers=other_owner_headers,
        ).status_code == 403

        listed = client.get("/therapists/public")
        assert listed.status_code == 200
        listed_ids = {item["id"] for item in listed.json()["items"]}
        assert therapist.id in listed_ids and other_therapist.id in listed_ids
        assert client.get(f"/therapists/public?practice_id={draft_practice.id}").json()["items"] == []
        assert client.get(f"/therapists/public?practice_id={unverified_practice.id}").json()["items"] == []
        verified_profile = client.post(f"/admin/therapists/{therapist.id}/verify", headers=admin_headers)
        assert verified_profile.status_code == 200
        assert client.post(f"/admin/therapists/{therapist.id}/verify", headers=owner_headers).status_code == 403
        assert client.get(f"/therapists/{therapist.id}/availability").status_code == 200
        assert client.get(f"/therapists/{unverified_therapist.id}/availability").status_code == 404

        created_slot = client.post(
            "/therapists/me/availability",
            json={"starts_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
                  "ends_at": (datetime.now(timezone.utc) + timedelta(days=3, minutes=50)).isoformat()},
            headers=therapist_headers,
        )
        assert created_slot.status_code == 200, created_slot.text
        assert client.post(
            "/therapists/me/availability",
            json={"starts_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
                  "ends_at": (datetime.now(timezone.utc) + timedelta(days=3, minutes=50)).isoformat()},
            headers=owner_headers,
        ).status_code == 403

        form_payload = {"fields": [{"id": "goals", "label": "What would you like support with?", "required": True}]}
        saved_form = client.put("/therapists/me/intake-form", json=form_payload, headers=therapist_headers)
        assert saved_form.status_code == 200, saved_form.text
        assert client.put("/therapists/me/intake-form", json=form_payload, headers=owner_headers).status_code == 403
        assert client.put("/therapists/me/intake-form", json=form_payload, headers=other_therapist_headers).status_code == 200

        smtp = MagicMock()
        smtp_context = MagicMock()
        smtp_context.__enter__.return_value = smtp
        smtp_context.__exit__.return_value = False
        with patch("backend.app.main.smtplib.SMTP", return_value=smtp_context):
            booking_response = client.post("/bookings", json={"availability_slot_id": slot.id}, headers=client_headers)
        assert booking_response.status_code == 200, booking_response.text
        booking = booking_response.json()
        assert booking["confirmation_email"] == "sent"
        assert smtp.send_message.call_count == 2
        assert client.post("/bookings", json={"availability_slot_id": slot.id}, headers=other_client_headers).status_code == 409
        assert client.post("/bookings", json={"availability_slot_id": other_slot.id}, headers=owner_headers).status_code == 403

        with SessionLocal() as db:
            duplicate = Booking(client_id=client_id, availability_slot_id=slot.id, status="confirmed")
            db.add(duplicate)
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()

        therapist_bookings = client.get("/therapists/me/bookings", headers=therapist_headers)
        assert therapist_bookings.status_code == 200
        assert {item["client"]["id"] for item in therapist_bookings.json()["items"]} == {client_id}
        assert client.get("/therapists/me/bookings", headers=other_therapist_headers).json()["items"] == []
        assert client.get("/therapists/me/bookings", headers=owner_headers).status_code == 403

        booking_id = booking["id"]
        assert client.get(f"/bookings/{booking_id}/intake-form", headers=client_headers).status_code == 200
        assert client.get(f"/bookings/{booking_id}/intake-form", headers=therapist_headers).status_code == 200
        assert client.get(f"/bookings/{booking_id}/intake-form", headers=other_client_headers).status_code == 403
        assert client.get(f"/bookings/{booking_id}/intake-form", headers=other_therapist_headers).status_code == 403
        assert client.get(f"/bookings/{booking_id}/intake-form", headers=owner_headers).status_code == 403
        assert client.get(f"/bookings/{booking_id}/intake-form", headers=other_owner_headers).status_code == 403

        submitted = client.post(
            f"/bookings/{booking_id}/intake-response",
            json={"answers": {"goals": "Fictional demo response"}},
            headers=client_headers,
        )
        assert submitted.status_code == 200, submitted.text
        assert client.get(f"/bookings/{booking_id}/intake-response", headers=therapist_headers).status_code == 200
        assert client.get(f"/bookings/{booking_id}/intake-response", headers=client_headers).status_code == 200
        assert client.get(f"/bookings/{booking_id}/intake-response", headers=other_client_headers).status_code == 403
        assert client.get(f"/bookings/{booking_id}/intake-response", headers=other_therapist_headers).status_code == 403
        assert client.get(f"/bookings/{booking_id}/intake-response", headers=owner_headers).status_code == 403
        assert client.get(f"/bookings/{booking_id}/intake-response", headers=other_owner_headers).status_code == 403
        assert client.post(f"/bookings/{booking_id}/intake-response", json={"answers": {}}, headers=therapist_headers).status_code == 403

        dashboard = client.get("/client/dashboard", headers=client_headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["practice"]["id"] == practice.id
        assert dashboard.json()["therapist"]["id"] == therapist.id
        assert dashboard.json()["upcoming_session"]["id"] == booking_id
        assert dashboard.json()["approved_exercises"] == []
        assert client.get("/client/dashboard", headers=other_client_headers).json()["upcoming_session"] is None
        assert client.get("/client/dashboard", headers=owner_headers).status_code == 403
        assert client.get("/client/dashboard", headers=therapist_headers).status_code == 403


def test_public_therapist_list_requires_both_verifications() -> None:
    with TestClient(app) as client:
        owner_token, owner_id = _register(client, "practice_owner")
        therapist_token, therapist_id = _register(client, "therapist")
        practice = _make_practice(owner_id, "Public Listing", verified=False)
        profile = _make_profile(therapist_id, practice.id, verified=True)
        listing = client.get("/therapists/public")
        assert profile.id not in {item["id"] for item in listing.json()["items"]}
        assert client.post(f"/admin/practices/{practice.id}/verify", headers=_headers(owner_token)).status_code == 403
        assert client.get(f"/therapists/{profile.id}/availability").status_code == 404
        assert client.get("/therapists/me/profile", headers=_headers(therapist_token)).status_code == 200
