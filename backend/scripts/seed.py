"""Idempotent seed. Synthetic, fictional data only (content lives in seed_data.py).

    python -m backend.scripts.seed            # seed (+ load KB)
    python -m backend.scripts.seed --check    # also print KB retrieval margins for the plateau client's notes
"""
from __future__ import annotations

import json
import secrets
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app import rag
from backend.app.auth import hash_password
from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.models import (Alert, Assessment, Assignment, AvailabilitySlot, Booking, CasePlan, Checkin, Exercise,
                                IntakeForm, IntakeResponse, PendingAction, Practice, TherapistProfile, TherapySession,
                                User)
from backend.scripts.seed_data import (COMMON_PAGE, CASES, INTAKE_FIELDS, LOGINS, PRACTICE_SLUGS, PRACTICES,
                                       THERAPISTS)

def _items(total: int, n: int) -> list[int]:
    """Spread total over the first n-1 (PHQ-9) or n items, 0-3 each. PHQ-9 item 9 stays 0 (no risk flag in seed)."""
    slots = n - 1 if n == 9 else n
    items = [0] * n
    for i in range(total):
        items[i % slots] += 1
    assert max(items) <= 3
    return items


def _user(db: Session, email: str, password: str, role: str, name: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(password), role=role, language="en", name=name,
                    is_verified=role in ("admin", "therapist"))
        db.add(user)
        db.flush()
    elif user.name != name:
        user.name = name
    return user


def _practice(db: Session, spec: dict, owner: User) -> Practice:
    practice = db.scalar(select(Practice).where(Practice.slug.in_([spec["slug"], spec["legacy"] or spec["slug"]])))
    page = json.dumps(COMMON_PAGE | spec["page"])
    if practice is None:
        practice = Practice(slug=spec["slug"], name=spec["name"], owner_id=owner.id, status="published", verified=True,
                            page_json=page)
        db.add(practice)
    else:  # existing databases: rename/refresh in place
        practice.slug, practice.name, practice.page_json = spec["slug"], spec["name"], page
    db.flush()
    return practice


def _profile(db: Session, user: User, practice: Practice, row: tuple) -> TherapistProfile:
    _, _, credentials, years, rating, reviews, fee, languages, approaches, specialisations, bio = row
    fields = dict(practice_id=practice.id, bio=bio, approaches=approaches, languages=languages, fee=fee, verified=True,
                  credentials=credentials, years_experience=years, rating=rating, review_count=reviews,
                  specialisations=specialisations)
    profile = db.scalar(select(TherapistProfile).where(TherapistProfile.user_id == user.id))
    if profile is None:
        profile = TherapistProfile(user_id=user.id, **fields)
        db.add(profile)
    else:
        for key, value in fields.items():
            setattr(profile, key, value)
    db.flush()
    if db.scalar(select(IntakeForm.id).where(IntakeForm.therapist_id == profile.id)) is None:
        db.add(IntakeForm(therapist_id=profile.id, fields_json=INTAKE_FIELDS))
    return profile


def _slot(db: Session, profile: TherapistProfile, start: datetime) -> AvailabilitySlot:
    slot = AvailabilitySlot(therapist_id=profile.id, starts_at=start, ends_at=start + timedelta(minutes=50))
    db.add(slot)
    db.flush()
    return slot


SLOT_TIMES_UTC = ((4, 30), (6, 30), (10, 30))  # minute 30 never collides with case slots (minutes 0-3)
SLOT_WINDOW_DAYS = 14


def refresh_slots(db: Session, profiles: list[TherapistProfile], now: datetime) -> None:
    """Idempotent: drop expired unbooked slots, add any missing slot in the next 14 days."""
    ids = [p.id for p in profiles]
    booked = select(Booking.availability_slot_id)
    db.execute(delete(AvailabilitySlot).where(AvailabilitySlot.therapist_id.in_(ids), AvailabilitySlot.starts_at <= now,
                                              AvailabilitySlot.id.not_in(booked)))
    end = now + timedelta(days=SLOT_WINDOW_DAYS)
    have = set(db.execute(select(AvailabilitySlot.therapist_id, AvailabilitySlot.starts_at)
                          .where(AvailabilitySlot.therapist_id.in_(ids), AvailabilitySlot.starts_at > now)).all())
    for profile in profiles:
        for d in range(SLOT_WINDOW_DAYS + 1):
            day = (now + timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
            for hour, minute in SLOT_TIMES_UTC:
                start = day.replace(hour=hour, minute=minute)
                if now < start <= end and (profile.id, start) not in have:
                    _slot(db, profile, start)


def _seed_client(db: Session, now: datetime, idx: int, client: User, therapist: User, profile: TherapistProfile,
                 spec: dict) -> None:
    if db.scalar(select(Booking.id).where(Booking.client_id == client.id).limit(1)) is not None:
        return  # already seeded; reruns never duplicate
    base = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=idx)  # idx keeps slots unique per therapist
    intake_pending = True

    def book(start: datetime) -> Booking:
        nonlocal intake_pending
        booking = Booking(client_id=client.id, availability_slot_id=_slot(db, profile, start).id)
        db.add(booking)
        db.flush()
        if intake_pending:
            db.add(IntakeResponse(booking_id=booking.id, client_id=client.id, answers_json=spec["intake"]))
            intake_pending = False
        return booking

    for days_ago, notes in spec["notes"]:
        start = base - timedelta(days=days_ago)
        session = TherapySession(booking_id=book(start).id, client_id=client.id, therapist_user_id=therapist.id,
                                 note_source="typed", raw_notes=notes, updated_at=start + timedelta(minutes=50))
        db.add(session)
        db.flush()
        rag.index_session_notes(db, therapist, client.id, session.id, notes)
    book(base + timedelta(hours=spec["future_hours"]))
    for kind, key, n in (("PHQ9", "phq9", 9), ("GAD7", "gad7", 7)):
        for days_ago, total in spec[key]:
            db.add(Assessment(client_id=client.id, recorded_by=therapist.id, type=kind, item_scores=_items(total, n),
                              total=total, taken_at=now - timedelta(days=days_ago, minutes=idx)))
    plan_age = max([22] + [d + 1 for d, _ in spec["notes"][:1]]) if spec["notes"] else 2
    db.add(CasePlan(client_id=client.id, therapist_user_id=therapist.id, version=1, approach=spec["approach"],
                    formulation_text=spec["formulation"], goals_json=spec["goals"],
                    approved_at=now - timedelta(days=plan_age), created_at=now - timedelta(days=plan_age)))
    for n, (days_ago, slug, done) in enumerate(spec["assignments"]):
        exercise = db.scalar(select(Exercise).where(Exercise.slug == slug))
        when = now - timedelta(days=days_ago)
        action = PendingAction(practice_id=profile.practice_id, type="release_exercise", status="approved",
                               assignee_user_id=therapist.id, decided_by=therapist.id, decided_at=when,
                               idempotency_key=f"seed:release:{client.id}:{n}", created_at=when.replace(tzinfo=None),
                               payload={"client_id": client.id, "exercise": slug, "seed": True})
        db.add(action)
        db.flush()
        assignment = Assignment(client_id=client.id, therapist_user_id=therapist.id, exercise_id=exercise.id,
                                pending_action_id=action.id, status="completed" if done else "assigned", created_at=when)
        db.add(assignment)
        db.flush()
        if done:
            db.add(Checkin(assignment_id=assignment.id, responses_json={"note": "Completed the short exercise."},
                           completed_at=when + timedelta(days=1)))
    for kind, days_ago, finding, detail, *acked in spec.get("alerts", []):
        when = now - timedelta(days=days_ago)
        payload = detail if kind == "risk" else {"finding": finding, "detail": detail, "date": when.date().isoformat()}
        db.add(Alert(therapist_user_id=therapist.id, client_id=client.id, type=kind, dedupe_key=f"seed:{client.id}:{kind}",
                     priority="high" if kind == "risk" else "normal", payload=payload, created_at=when,
                     acknowledged=bool(acked and acked[0]), acknowledged_at=when + timedelta(hours=6) if acked and acked[0] else None))
    for kind, extra in spec.get("pending", []):
        db.add(PendingAction(practice_id=profile.practice_id, type=kind, status="pending", assignee_user_id=therapist.id,
                             idempotency_key=f"seed:pending:{client.id}:{kind}:{extra['exercise']}",
                             payload={"client_id": client.id, "seed": True, **extra}))


HISTORY_WEEKS = 26
HISTORY_TIMES_UTC = ((5, 45), (7, 45), (9, 45))  # minute 45: no clash with case (0-3) or open (30) slots
PAST_CLIENTS_PER_THERAPIST = 2
_FIRST = ["Aarav", "Diya", "Vivaan", "Meera", "Kabir", "Ira", "Reyansh", "Tara", "Arnav", "Saanvi", "Dev", "Navya",
          "Yash", "Anika", "Neel", "Kiara", "Om", "Riya"]
_LAST = ["Shah", "Nair", "Gowda", "Kapoor", "Pillai", "Sharma", "Rao", "Menon", "Iyer"]


def seed_history(db: Session, now: datetime, profiles: dict[str, TherapistProfile]) -> None:
    """Idempotent: ~6 months of past sessions so practice analytics have a history. They belong to separate past
    clients (no assessments, notes or plans), so no existing client gains a therapist and nothing clinical is added."""
    for t, profile in enumerate(profiles.values()):
        clients = []
        for j in range(PAST_CLIENTS_PER_THERAPIST):
            n = t * PAST_CLIENTS_PER_THERAPIST + j
            email = f"past.client{n + 1}@example.com"
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, password_hash=hash_password(secrets.token_hex(16)), role="client", language="en",
                            name=f"{_FIRST[n % len(_FIRST)]} {_LAST[(n * 5) % len(_LAST)]}")
                db.add(user)
                db.flush()
            clients.append(user.id)
        have = set(db.scalars(select(AvailabilitySlot.starts_at).where(AvailabilitySlot.therapist_id == profile.id)))
        n = 0
        for week in range(1, HISTORY_WEEKS + 1):
            day = (now - timedelta(weeks=week)).replace(hour=0, minute=0, second=0, microsecond=0)
            for k in range(1 + (week + t) % 3):
                hour, minute = HISTORY_TIMES_UTC[k]
                start = (day + timedelta(days=(week + k + t) % 5)).replace(hour=hour, minute=minute)
                if start in have:
                    continue
                db.add(Booking(client_id=clients[n % len(clients)], availability_slot_id=_slot(db, profile, start).id))
                n += 1
        db.flush()


def seed(db: Session, *, load_kb: bool = True, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    users = {email: _user(db, email, pw, role, name) for email, pw, role, name in LOGINS}
    practices = {p["slug"]: _practice(db, p, users[p["owner"]]) for p in PRACTICES}
    profiles = {row[0]: _profile(db, users[row[0]], practices[row[1]], row) for row in THERAPISTS}
    if load_kb:
        db.commit()
        rag.load_kb(db)
    for idx, (email, spec) in enumerate(CASES.items()):
        if spec is not None:
            _seed_client(db, now, idx, users[email], users[spec["therapist"]], profiles[spec["therapist"]], spec)
    seed_history(db, now, profiles)
    refresh_slots(db, list(profiles.values()), now)
    db.commit()


def check_retrieval(db: Session) -> bool:
    """Real-embedder check: the plateau client's notes must retrieve KB entries above KB_MIN_SIMILARITY."""
    spec = CASES["client@example.com"]
    queries = [("goals", " ".join(g["text"] for g in spec["goals"][:1]))] + \
              [(f"notes {d}d ago", text) for d, text in spec["notes"]]
    ok = True
    print(f"KB_MIN_SIMILARITY = {settings.kb_min_similarity}")
    for label, query in queries:
        hits = rag.retrieve_knowledge(db, query, k=3, min_similarity=0.0)
        top = hits[0] if hits else None
        margin = (top.similarity - settings.kb_min_similarity) if top else float("-inf")
        ok &= margin > 0
        print(f"  {label:<14} top={top.title if top else None!s:<36} sim={top.similarity if top else 0:.3f} margin={margin:+.3f}")
    from backend.app.clinical import scan_client_text
    flagged = [t for c in CASES.values() if c for t in [n for _, n in c["notes"]] + list(c["intake"].values())
               if scan_client_text(t)]
    print(f"  seed text flagged by the real safety layer: {len(flagged)}")
    for t in flagged:
        print("    -", t[:90])
    return ok and not flagged


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
        print("Seed complete")
        for email, password, role, _ in LOGINS:
            print(f"  {role:<15} {email:<26} {password}")
        if "--check" in sys.argv:
            sys.exit(0 if check_retrieval(session) else 1)
