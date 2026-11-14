from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import AvailabilitySlot, Booking, Practice, TherapistProfile, User


@pytest.fixture
def scenario():
    with TestClient(app) as client:
        identities = {}
        for role, key in [
            ("client", "client"), ("client", "other_client"),
            ("therapist", "therapist_a"), ("therapist", "therapist_b"),
            ("therapist", "therapist_c"), ("therapist", "therapist_d"),
            ("therapist", "unverified_therapist"),
            ("practice_owner", "owner_a"), ("practice_owner", "owner_b"),
            ("admin", "admin"),
        ]:
            email = f"{key}-{uuid4().hex}@example.com"
            response = client.post("/auth/register", json={
                "email": email, "password": "secret1234", "role": "client" if role == "admin" else role,
                "language": "en", "name": key.replace("_", " ").title(),
            })
            assert response.status_code == 200, response.text
            if role == "admin":  # admins cannot self-register; promote directly in the DB
                with SessionLocal() as db:
                    db.query(User).filter(User.email == email).update({"role": "admin", "is_verified": True})
                    db.commit()
            login = client.post("/auth/login", json={"email": email, "password": "secret1234"})
            user_id = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['token']}"}).json()["id"]
            identities[key] = {"id": user_id, "token": login.json()["token"], "email": email}
            client.cookies.clear()

        def make_practice(name: str, owner: str, status: str = "published", verified: bool = True) -> Practice:
            with SessionLocal() as db:
                row = Practice(name=name, slug=f"{uuid4().hex}", owner_id=identities[owner]["id"],
                               status=status, verified=verified, page_json="{}")
                db.add(row)
                db.commit()
                db.refresh(row)
                return row

        def make_profile(user: str, practice: Practice, verified: bool = True) -> TherapistProfile:
            with SessionLocal() as db:
                row = TherapistProfile(user_id=identities[user]["id"], practice_id=practice.id,
                                       bio="Demo therapist", approaches=["CBT"], languages=["en"],
                                       fee=2000, verified=verified)
                db.add(row)
                db.commit()
                db.refresh(row)
                return row

        def make_slot(profile: TherapistProfile) -> AvailabilitySlot:
            with SessionLocal() as db:
                starts = datetime.now(timezone.utc) + timedelta(days=2)
                row = AvailabilitySlot(therapist_id=profile.id, starts_at=starts,
                                       ends_at=starts + timedelta(minutes=50))
                db.add(row)
                db.commit()
                db.refresh(row)
                return row

        practice_a = make_practice("Practice A", "owner_a")
        practice_b = make_practice("Practice B", "owner_b")
        practice_unverified = make_practice("Unverified Practice", "owner_a", verified=False)
        practice_draft = make_practice("Draft Practice", "owner_a", status="draft")
        therapist_a = make_profile("therapist_a", practice_a)
        therapist_b = make_profile("therapist_b", practice_b)
        therapist_unverified_practice = make_profile("therapist_c", practice_unverified)
        therapist_draft_practice = make_profile("therapist_d", practice_draft)
        therapist_unverified = make_profile("unverified_therapist", practice_a, verified=False)
        slot_a = make_slot(therapist_a)
        slot_b = make_slot(therapist_b)
        yield locals() | {"client": client}


def headers(scenario, identity: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {scenario['identities'][identity]['token']}"}


def make_intake_and_booking(scenario, therapist: str, slot: AvailabilitySlot, client_identity: str = "client") -> int:
    client = scenario["client"]
    saved = client.put("/therapists/me/intake-form",
                       json={"fields": [{"id": "goals", "label": "Goals", "required": True}]},
                       headers=headers(scenario, therapist))
    assert saved.status_code == 200, saved.text
    booking = client.post("/bookings", json={"availability_slot_id": slot.id},
                          headers=headers(scenario, client_identity))
    assert booking.status_code == 200, booking.text
    response = client.post(f"/bookings/{booking.json()['id']}/intake-response",
                           json={"answers": {"goals": "Fictional concern sentinel"}},
                           headers=headers(scenario, client_identity))
    assert response.status_code == 200, response.text
    return booking.json()["id"]


def test_therapist_can_manage_own_profile_but_owner_cannot(scenario) -> None:
    client = scenario["client"]
    response = client.post("/therapists/me/profile", json={
        "practice_id": scenario["practice_a"].id, "bio": "Updated", "approaches": ["CBT"],
        "languages": ["en"], "fee": 2500,
    }, headers=headers(scenario, "therapist_a"))
    assert response.status_code == 200
    assert client.get("/therapists/me/profile", headers=headers(scenario, "owner_a")).status_code == 403


def test_unverified_therapist_is_excluded_from_public_listing(scenario) -> None:
    result = scenario["client"].get("/therapists/public")
    ids = {item["id"] for item in result.json()["items"]}
    assert scenario["therapist_a"].id in ids
    assert scenario["therapist_unverified"].id not in ids


def test_verified_therapist_at_unverified_practice_is_excluded(scenario) -> None:
    ids = {item["id"] for item in scenario["client"].get("/therapists/public").json()["items"]}
    assert scenario["therapist_unverified_practice"].id not in ids


def test_verified_therapist_at_draft_practice_is_excluded(scenario) -> None:
    ids = {item["id"] for item in scenario["client"].get("/therapists/public").json()["items"]}
    assert scenario["therapist_draft_practice"].id not in ids


def test_practice_owner_cannot_access_another_practices_bookings_or_intake(scenario) -> None:
    booking_id = make_intake_and_booking(scenario, "therapist_b", scenario["slot_b"], "other_client")
    client = scenario["client"]
    owner = headers(scenario, "owner_a")
    assert client.post("/therapists/me/profile", json={
        "practice_id": scenario["practice_b"].id, "bio": "Attempt", "approaches": [],
        "languages": [], "fee": 1000,
    }, headers=owner).status_code == 403
    assert client.get("/therapists/me/bookings", headers=owner).status_code == 403
    assert client.post("/bookings", json={"availability_slot_id": scenario["slot_b"].id},
                       headers=owner).status_code == 403
    assert client.put("/therapists/me/intake-form", json={
        "fields": [{"id": "secret", "label": "Private", "required": True}],
    }, headers=owner).status_code == 403
    assert client.get(f"/bookings/{booking_id}/intake-form", headers=owner).status_code == 403
    assert client.get(f"/bookings/{booking_id}/intake-response", headers=owner).status_code == 403
    assert client.get(f"/therapists/{scenario['therapist_b'].id}/availability", headers=owner).status_code in {403, 404}
    assert client.get(f"/therapists/{scenario['therapist_b'].id}/availability").status_code == 200
    assert client.get(f"/therapists/{scenario['therapist_b'].id}/availability",
                      headers=headers(scenario, "client")).status_code == 200
    assert client.post("/therapists/me/availability", json={
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
        "ends_at": (datetime.now(timezone.utc) + timedelta(days=4, minutes=50)).isoformat(),
    }, headers=owner).status_code == 403
    assert client.post(f"/admin/therapists/{scenario['therapist_b'].id}/verify", headers=owner).status_code == 403


def test_client_cannot_read_another_clients_intake_or_dashboard(scenario) -> None:
    booking_id = make_intake_and_booking(scenario, "therapist_a", scenario["slot_a"])
    client = scenario["client"]
    other = headers(scenario, "other_client")
    assert client.get(f"/bookings/{booking_id}/intake-form", headers=other).status_code == 403
    assert client.get(f"/bookings/{booking_id}/intake-response", headers=other).status_code == 403
    assert client.get("/client/dashboard", headers=other).json()["upcoming_session"] is None


def test_therapist_without_booking_cannot_read_intake_response(scenario) -> None:
    booking_id = make_intake_and_booking(scenario, "therapist_a", scenario["slot_a"])
    response = scenario["client"].get(f"/bookings/{booking_id}/intake-response",
                                      headers=headers(scenario, "therapist_b"))
    assert response.status_code == 403


def test_client_cannot_read_another_therapists_intake_response(scenario) -> None:
    booking_id = make_intake_and_booking(scenario, "therapist_b", scenario["slot_b"], "other_client")
    response = scenario["client"].get(f"/bookings/{booking_id}/intake-response",
                                      headers=headers(scenario, "client"))
    assert response.status_code == 403


def test_therapist_sees_only_bookings_with_them(scenario) -> None:
    make_intake_and_booking(scenario, "therapist_a", scenario["slot_a"])
    result = scenario["client"].get("/therapists/me/bookings", headers=headers(scenario, "therapist_b"))
    assert result.status_code == 200
    assert result.json()["items"] == []


def test_client_dashboard_returns_own_practice_therapist_session_and_empty_exercises(scenario) -> None:
    booking = scenario["client"].post("/bookings", json={"availability_slot_id": scenario["slot_a"].id},
                                      headers=headers(scenario, "client"))
    result = scenario["client"].get("/client/dashboard", headers=headers(scenario, "client"))
    assert result.status_code == 200
    assert result.json()["practice"]["id"] == scenario["practice_a"].id
    assert result.json()["therapist"]["id"] == scenario["therapist_a"].id
    assert result.json()["upcoming_session"]["id"] == booking.json()["id"]
    assert result.json()["approved_exercises"] == []


def test_double_booking_same_slot_fails_and_unique_constraint_enforces_it(scenario) -> None:
    first = scenario["client"].post("/bookings", json={"availability_slot_id": scenario["slot_a"].id},
                                    headers=headers(scenario, "client"))
    second = scenario["client"].post("/bookings", json={"availability_slot_id": scenario["slot_a"].id},
                                     headers=headers(scenario, "other_client"))
    assert first.status_code == 200
    assert second.status_code == 409
    with SessionLocal() as db:
        db.add(Booking(client_id=scenario["identities"]["other_client"]["id"],
                       availability_slot_id=scenario["slot_a"].id, status="confirmed"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_confirmation_emails_are_exactly_once_per_recipient_and_contain_no_clinical_data(monkeypatch, scenario) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_USER", "demo-user")
    monkeypatch.setenv("SMTP_PASS", "demo-pass")
    monkeypatch.setenv("SMTP_FROM", "demo@example.com")
    smtp = MagicMock()
    smtp_context = MagicMock()
    smtp_context.__enter__.return_value = smtp
    smtp_context.__exit__.return_value = False
    with patch("backend.app.main.smtplib.SMTP", return_value=smtp_context):
        result = scenario["client"].post("/bookings", json={"availability_slot_id": scenario["slot_a"].id},
                                         headers=headers(scenario, "client"))
        assert result.status_code == 200, result.text
        failed_booking = scenario["client"].post("/bookings", json={"availability_slot_id": scenario["slot_a"].id},
                                                  headers=headers(scenario, "other_client"))
        retry = scenario["client"].post("/bookings", json={"availability_slot_id": scenario["slot_a"].id},
                                         headers=headers(scenario, "client"))

    assert failed_booking.status_code == 409
    assert retry.status_code == 409
    assert smtp.send_message.call_count == 2
    messages: list[EmailMessage] = [call.args[0] for call in smtp.send_message.call_args_list]
    recipients = {message["To"] for message in messages}
    assert recipients == {scenario["identities"]["client"]["email"], scenario["identities"]["therapist_a"]["email"]}
    assert len({message["To"] for message in messages}) == 2
    time_text = result.json()["starts_at"]
    for message in messages:
        assert message.get_content() == (
            f"Practice: {scenario['practice_a'].name}\n"
            f"Therapist: Therapist A\n"
            f"Session time: {time_text}\n"
        )


