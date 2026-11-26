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
                row = db.query(TherapistProfile).filter(TherapistProfile.user_id == identities[user]["id"]).first()
                if row is None:  # therapist signup already created a draft profile
                    row = TherapistProfile(user_id=identities[user]["id"])
                    db.add(row)
                row.practice_id, row.bio, row.approaches, row.languages = practice.id, "Demo therapist", ["CBT"], ["en"]
                row.fee, row.verified = 2000, verified
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
        "bio": "Updated", "approaches": ["CBT"],
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
        "bio": "Attempt", "approaches": [],
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
    assert client.post(f"/admin/therapists/{scenario['therapist_b'].id}/review", json={"decision": "verified"}, headers=owner).status_code == 403


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




def _book(scenario, slot, who="client") -> int:
    r = scenario["client"].post("/bookings", json={"availability_slot_id": slot.id}, headers=headers(scenario, who))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_booking_room_only_for_its_client_and_therapist(scenario) -> None:
    c = scenario["client"]
    booking_id = _book(scenario, scenario["slot_a"])
    for who in ("client", "therapist_a"):
        r = c.get(f"/bookings/{booking_id}/room", headers=headers(scenario, who))
        assert r.status_code == 200 and r.json()["room_name"].startswith("cp-")
    for who in ("other_client", "therapist_b", "owner_a", "owner_b"):
        assert c.get(f"/bookings/{booking_id}/room", headers=headers(scenario, who)).status_code in {403, 404}, who
    assert c.get(f"/bookings/{booking_id}/room").status_code in {401, 403}


def test_room_name_unique_per_booking_and_not_derived_from_id(scenario) -> None:
    c = scenario["client"]
    id_a = _book(scenario, scenario["slot_a"])
    id_b = _book(scenario, scenario["slot_b"], "other_client")
    room_a = c.get(f"/bookings/{id_a}/room", headers=headers(scenario, "client")).json()["room_name"]
    room_b = c.get(f"/bookings/{id_b}/room", headers=headers(scenario, "other_client")).json()["room_name"]
    assert room_a != room_b
    for room, bid in ((room_a, id_a), (room_b, id_b)):
        assert len(room) >= 3 + 32 and str(bid) not in room.removeprefix("cp-")[:8]
        assert room != f"cp-{bid}" and "booking" not in room


def test_public_therapist_filters_and_detail_expose_only_published_verified(scenario) -> None:
    client = scenario["client"]
    with SessionLocal() as db:
        db.query(Practice).filter(Practice.id == scenario["practice_a"].id).update({"page_json": '{"location": "Bengaluru"}'})
        db.query(TherapistProfile).filter(TherapistProfile.id == scenario["therapist_a"].id).update(
            {"languages": ["en", "hi"], "specialisations": ["Sleep"]})
        db.query(TherapistProfile).filter(TherapistProfile.id == scenario["therapist_unverified"].id).update(
            {"languages": ["hi"], "specialisations": ["Sleep"]})
        db.query(TherapistProfile).filter(TherapistProfile.id == scenario["therapist_draft_practice"].id).update(
            {"languages": ["hi"], "specialisations": ["Sleep"]})
        db.commit()
    result = client.get("/therapists/public", params={"city": "bengal", "language": "HI", "specialisation": "sleep"})
    items = result.json()["items"]
    assert [i["id"] for i in items] == [scenario["therapist_a"].id]
    assert client.get("/therapists/public", params={"city": "Pune"}).json()["items"] == []
    ids = [i["id"] for i in client.get("/therapists/public", params={"language": "hi", "specialisation": "sleep"}).json()["items"]]
    assert scenario["therapist_a"].id in ids
    assert scenario["therapist_unverified"].id not in ids and scenario["therapist_draft_practice"].id not in ids
    for key in ("therapist_unverified", "therapist_draft_practice", "therapist_unverified_practice"):
        assert client.get(f"/therapists/public/{scenario[key].id}").status_code == 404
    detail = client.get(f"/therapists/public/{scenario['therapist_a'].id}").json()
    assert detail["id"] == scenario["therapist_a"].id
    blob = str(items) + str(detail)
    for leak in ("email", "password", "user_id", scenario["identities"]["client"]["email"]):
        assert leak not in blob


def test_public_practice_city_and_specialisation_filters_only_published_verified(scenario) -> None:
    client = scenario["client"]
    page = '{"location": "Mysuru", "specialties": ["sleep"]}'
    with SessionLocal() as db:
        db.query(Practice).filter(Practice.id.in_([scenario["practice_b"].id, scenario["practice_unverified"].id,
                                                   scenario["practice_draft"].id])).update({"page_json": page})
        db.commit()
    ids = {i["id"] for i in client.get("/practices/public", params={"city": "mysuru", "specialisation": "Sleep"}).json()["items"]}
    assert ids == {scenario["practice_b"].id}
