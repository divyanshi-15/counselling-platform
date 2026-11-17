from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app.auth import create_access_token
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Booking, Practice, User
from backend.scripts import seed as seed_mod

client = TestClient(app)


@pytest.fixture
def seeded():
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS]) | User.email.like("past.client%@example.com")))
            db.execute(delete(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS)))
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


PRACTICE_KEYS = {"bookings_per_week", "utilisation_next_14_days", "revenue_per_month", "top_specialisations"}


@pytest.mark.parametrize("path", ["/analytics/therapist", "/analytics/practice"])
def test_unauthenticated_401(seeded, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/analytics/therapist", "/analytics/practice"])
def test_client_and_admin_403(seeded, path):
    for who in ("client@example.com", "admin@example.com"):
        assert client.get(path, headers=_h(who)).status_code == 403


def test_owner_cannot_read_therapist_analytics(seeded):
    assert client.get("/analytics/therapist", headers=_h("owner@example.com")).status_code == 403


def test_therapist_cannot_read_practice_analytics(seeded):
    assert client.get("/analytics/practice", headers=_h("therapist@example.com")).status_code == 403


def test_therapist_sees_only_own_clients(seeded):
    a = client.get("/analytics/therapist", headers=_h("therapist@example.com")).json()
    b = client.get("/analytics/therapist", headers=_h("therapist2@example.com")).json()  # same practice
    names_a, names_b = {c["name"] for c in a["clients"]}, {c["name"] for c in b["clients"]}
    assert names_a == {"Ananya Rao", "Rohan Mehta"} and names_b == {"Ishaan Verma"}
    assert isinstance(a["open_alerts"], int)
    alpha = next(c for c in a["clients"] if c["name"] == "Ananya Rao")
    assert alpha["phq9"]["latest"] == 15 and alpha["phq9"]["change"] < 0 and len(alpha["phq9"]["points"]) >= 5
    assert a["sessions_completed"]["last_30_days"] > 0 and a["upcoming_sessions_7_days"] >= 1
    assert 0 <= a["exercise_completion_rate"] <= 1


def test_practice_payload_has_no_clinical_fields(seeded):
    body = client.get("/analytics/practice", headers=_h("owner@example.com")).json()
    assert set(body) == PRACTICE_KEYS
    assert set(body["bookings_per_week"][0]) == {"week_start", "bookings"}
    assert set(body["revenue_per_month"][0]) == {"month", "sessions", "revenue_inr"}
    assert set(body["utilisation_next_14_days"]) == {"booked_slots", "available_slots", "utilisation", "by_therapist"}
    assert set(body["utilisation_next_14_days"]["by_therapist"][0]) == {"therapist", "booked_slots", "available_slots", "utilisation"}
    assert set(body["top_specialisations"][0]) == {"specialisation", "bookings"}
    text = str(body).lower()
    for banned in ("phq", "gad", "alert", "note", "score", "client", "ananya rao", "rohan mehta"):
        assert banned not in text


def test_practice_owner_scoped_to_own_practice(seeded):
    x = client.get("/analytics/practice", headers=_h("owner@example.com")).json()
    y = client.get("/analytics/practice", headers=_h("owner2@example.com")).json()
    assert len(x["bookings_per_week"]) == 12 and len(x["revenue_per_month"]) == 6
    with SessionLocal() as db:
        def sessions(owner: str) -> int:
            from backend.app.models import AvailabilitySlot, TherapistProfile
            return db.scalar(select(func.count(Booking.id)).join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
                             .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
                             .join(Practice, Practice.id == TherapistProfile.practice_id)
                             .join(User, User.id == Practice.owner_id).where(User.email == owner))
        assert sum(m["sessions"] for m in x["revenue_per_month"]) <= sessions("owner@example.com")
        assert sum(m["sessions"] for m in y["revenue_per_month"]) <= sessions("owner2@example.com")
    assert {t["therapist"] for t in x["utilisation_next_14_days"]["by_therapist"]} == {"Dr Meera Krishnan", "Arjun Nair", "Dr Kavya Shetty"}
    assert {t["therapist"] for t in y["utilisation_next_14_days"]["by_therapist"]} == {"Rohan Hegde", "Sneha Gowda", "Dr Anand Murthy"}
    assert x != y and sum(m["revenue_inr"] for m in x["revenue_per_month"]) > 0 and x["top_specialisations"]


def test_seed_history_is_idempotent(seeded):
    with SessionLocal() as db:
        before = db.scalar(select(func.count(Booking.id)))
        seed_mod.seed(db, load_kb=False)
        assert db.scalar(select(func.count(Booking.id))) == before
