from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app import rag
from backend.app.agents import copilot
from backend.app.auth import create_access_token
from backend.app.citations import Suggestion
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import AvailabilitySlot, Booking, KbChunk, KbDocument, Practice, TherapistProfile, User
from backend.scripts import seed as seed_mod

client = TestClient(app)
T0 = datetime(2030, 3, 4, 8, 0, tzinfo=timezone.utc)  # frozen clock


@pytest.fixture
def seeded():
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS])))
            db.execute(delete(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS)))
            db.commit()
    wipe()
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False, now=T0)
    yield
    wipe()


def _h(email: str) -> dict[str, str]:
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        return {"Authorization": f"Bearer {create_access_token(u.email, u.role)}"}


def _slots(db, email: str) -> list[AvailabilitySlot]:
    return list(db.scalars(select(AvailabilitySlot).join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
                           .join(User, User.id == TherapistProfile.user_id).where(User.email == email)
                           .order_by(AvailabilitySlot.starts_at)))


def _generated(db, email: str, now: datetime) -> list[datetime]:
    return [s.starts_at for s in _slots(db, email) if s.starts_at.minute == 30 and s.starts_at > now]


def test_seed_slots_next_14_days_several_per_therapist(seeded):
    with SessionLocal() as db:
        for email in ("therapist@example.com", "therapist2@example.com", "therapist3@example.com",
                      "therapist9@example.com"):
            starts = _generated(db, email, T0)
            assert len(starts) >= 14 * 3 - 3
            assert all(T0 < s <= T0 + timedelta(days=14) for s in starts)


def test_seed_rerun_same_time_is_idempotent(seeded):
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(AvailabilitySlot))
        seed_mod.seed(db, load_kb=False, now=T0)
        assert db.scalar(select(func.count()).select_from(AvailabilitySlot)) == before


def test_seed_rerun_later_refreshes_expired_slots_and_keeps_booked(seeded):
    later = T0 + timedelta(days=5, hours=3)
    with SessionLocal() as db:
        booked_ids = {b for (b,) in db.query(Booking.availability_slot_id).all()}
        seed_mod.seed(db, load_kb=False, now=later)
        booked_now = {b for (b,) in db.query(Booking.availability_slot_id).all()}
        gen = _generated(db, "therapist@example.com", later)
        assert gen and all(later < s <= later + timedelta(days=14) for s in gen)
        assert max(gen) > T0 + timedelta(days=14)  # window moved forward
        expired_unbooked = [s for s in _slots(db, "therapist@example.com") if s.starts_at <= later and s.id not in booked_now]
        assert expired_unbooked == []
        assert booked_ids <= set(db.scalars(select(AvailabilitySlot.id)))  # past booked sessions survive
        count = db.scalar(select(func.count()).select_from(AvailabilitySlot))
        seed_mod.seed(db, load_kb=False, now=later)
        assert db.scalar(select(func.count()).select_from(AvailabilitySlot)) == count


def _new_slot(email: str, days: int = 20) -> int:
    start = datetime.now(timezone.utc) + timedelta(days=days)
    r = client.post("/therapists/me/availability", headers=_h(email),
                    json={"starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=50)).isoformat()})
    assert r.status_code == 200
    return r.json()["id"]


def test_only_slot_owner_can_change_it(seeded):
    sid = _new_slot("therapist@example.com")
    url = f"/therapists/me/availability/{sid}"
    assert client.delete(url).status_code == 401
    for email in ("therapist2@example.com", "client@example.com", "owner@example.com", "admin@example.com"):
        assert client.delete(url, headers=_h(email)).status_code == 403
    r2 = client.get("/therapists/me/availability", headers=_h("therapist2@example.com"))
    assert r2.status_code == 200, r2.text
    other = r2.json()["items"]
    assert sid not in [i["id"] for i in other]
    mine = client.get("/therapists/me/availability", headers=_h("therapist@example.com")).json()["items"]
    assert sid in [i["id"] for i in mine]
    assert client.get("/therapists/me/availability", headers=_h("client@example.com")).status_code == 403
    assert client.get("/therapists/me/availability", headers=_h("owner@example.com")).status_code == 403
    assert client.delete(url, headers=_h("therapist@example.com")).status_code == 204
    assert client.delete(url, headers=_h("therapist@example.com")).status_code == 404


def test_booked_slot_cannot_be_removed(seeded):
    sid = _new_slot("therapist@example.com")
    assert client.post("/bookings", headers=_h("client@example.com"), json={"availability_slot_id": sid}).status_code in (200, 201)
    assert client.delete(f"/therapists/me/availability/{sid}", headers=_h("therapist@example.com")).status_code == 409


def test_sleep_racing_worry_citations_map_to_worry_postponement(seeded):
    with SessionLocal() as db:
        rag.load_kb(db)
        def chunk(slug: str) -> int:
            return db.scalars(select(KbChunk.id).join(KbDocument, KbDocument.id == KbChunk.document_id)
                              .where(KbDocument.slug == slug)).first()
        for slug in ("worry-postponement", "stimulus-control", "wind-down-routine"):
            got = copilot._release_candidates(db, [Suggestion(text="x", chunk_ids=[chunk(slug)])])
            assert got == [("worry_postponement", 0)], slug
        assert copilot._release_candidates(db, [Suggestion(text="x", chunk_ids=[chunk("thought-record")])]) == [("thought_record", 0)]
        assert copilot._release_candidates(db, [Suggestion(text="x", chunk_ids=[chunk("slow-breathing")])]) == []


def test_seed_shape_is_a_populated_product(seeded):
    from backend.app.models import Alert, Assessment, PendingAction
    emails = [row[0] for row in seed_mod.LOGINS]
    with SessionLocal() as db:
        clients = db.scalars(select(User.id).where(User.email.in_(emails), User.role == "client")).all()
        assert len(clients) == 12
        assert db.scalar(select(func.count(Booking.id)).where(Booking.client_id.in_(clients))) == 40
        assert db.scalar(select(func.count(TherapistProfile.id))) >= 9
        profiles = db.scalars(select(TherapistProfile).join(User, User.id == TherapistProfile.user_id)
                              .where(User.email.in_(emails))).all()
        assert len(profiles) == 9 and all(p.credentials and p.rating and p.years_experience for p in profiles)
        assert len(db.scalars(select(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS))).all()) == 3
        long_history = [c for c in clients if db.scalar(select(func.count(Assessment.id)).where(
            Assessment.client_id == c, Assessment.type == "PHQ9", Assessment.taken_at < T0 - timedelta(days=150))) > 0]
        assert len(long_history) == 4
        assert db.scalar(select(func.count(Alert.id)).where(Alert.client_id.in_(clients))) >= 4
        assert db.scalar(select(func.count(PendingAction.id)).where(PendingAction.status == "pending")) >= 3
