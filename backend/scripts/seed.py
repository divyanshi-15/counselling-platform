"""Idempotent seed. Synthetic, fictional data only (content lives in seed_data.py).

    python -m backend.scripts.seed            # seed (+ load KB)
    python -m backend.scripts.seed --check    # also print KB retrieval margins for the plateau client's notes
"""
from __future__ import annotations

import json
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app import rag
from backend.app.auth import hash_password
from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.models import (Alert, Assessment, Assignment, AvailabilitySlot, Booking, CasePlan, Checkin, Exercise,
                                IntakeForm, IntakeResponse, Journey, JourneyAssignment, JourneyStep, JourneyStepProgress, MoodCheckin, PendingAction, Practice, PracticeInvite, TherapistEducation, TherapistLicense,
                                TherapistProfile, TherapySession, User, VerificationDocument)
from backend.app.practice_setup import _hash_token, INVITE_DAYS, set_practice_status
from backend.app.verification import OWNER_TYPE, set_status, store_document, upload_dir
from backend.scripts.seed_data import (COMMON_PAGE, CASES, INTAKE_FIELDS, JOURNEYS, JOURNEY_ASSIGNMENT, LOGINS, PENDING_THERAPIST, PRACTICE_SLUGS,
                                       PRACTICES, PRACTICE_DETAILS, SETUP_INVITE, SETUP_PRACTICE, THERAPISTS, VERIFICATION)

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
    set_practice_status(practice, "verified")
    d = PRACTICE_DETAILS[spec["slug"]]
    practice.languages = spec["page"]["languages"]
    for key, value in d.items():
        setattr(practice, key, value)
    db.flush()
    return practice


def _setup_practice(db: Session, now: datetime, users: dict[str, User]) -> None:
    """Idempotent: a draft practice with saved details and an AI-proposed page, plus one pending invitation."""
    spec = SETUP_PRACTICE
    practice = db.scalar(select(Practice).where(Practice.slug == spec["slug"]))
    if practice is None:
        practice = Practice(slug=spec["slug"], name=spec["name"], owner_id=users[spec["owner"]].id, status="draft",
                            verified=False, page_json="{}")
        db.add(practice)
        for key, value in spec["details"].items():
            setattr(practice, key, value)
        practice.page_tagline, practice.page_text, practice.page_source = spec["tagline"], spec["text"], "ai"
        practice.page_updated_at = now
        db.flush()
        inputs = {"name": practice.name, **{k: v for k, v in spec["details"].items() if k != "address"}}
        practice.page_inputs = inputs
        set_practice_status(practice, "draft")
    practice.owner_id = users[spec["owner"]].id
    invite = db.scalar(select(PracticeInvite).where(PracticeInvite.token_hash == _hash_token(SETUP_INVITE["token"])))
    if invite is None:
        db.add(PracticeInvite(practice_id=practice.id, email=SETUP_INVITE["email"], status="pending",
                              token_hash=_hash_token(SETUP_INVITE["token"]), created_by=practice.owner_id,
                              expires_at=now + timedelta(days=INVITE_DAYS), idempotency_key="seed-invite-1"))
    elif invite.status == "pending":
        invite.expires_at = now + timedelta(days=INVITE_DAYS)
    db.flush()


def _profile(db: Session, user: User, practice: Practice, row: tuple, status: str = "verified") -> TherapistProfile:
    _, _, credentials, years, rating, reviews, fee, languages, approaches, specialisations, bio = row
    fields = dict(practice_id=practice.id, bio=bio, approaches=approaches, languages=languages, fee=fee,
                  credentials=credentials, years_experience=years, rating=rating, review_count=reviews,
                  specialisations=specialisations)
    profile = db.scalar(select(TherapistProfile).where(TherapistProfile.user_id == user.id))
    if profile is None:
        profile = TherapistProfile(user_id=user.id, **fields)
        db.add(profile)
        set_status(profile, status)
        if status == "submitted":
            profile.submitted_at = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        for key, value in fields.items():
            setattr(profile, key, value)
        if status == "verified":  # a pending profile keeps whatever state the admin review left it in
            set_status(profile, "verified")
    db.flush()
    _credentials(db, profile, user, status)
    if db.scalar(select(IntakeForm.id).where(IntakeForm.therapist_id == profile.id)) is None:
        db.add(IntakeForm(therapist_id=profile.id, fields_json=INTAKE_FIELDS))
    return profile


def _placeholder_pdf(title: str) -> bytes:
    """Tiny valid one-page PDF standing in for a scanned certificate."""
    text = f"BT /F1 14 Tf 72 720 Td ({title}) Tj ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(text)} >>\nstream\n{text}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def _credentials(db: Session, profile: TherapistProfile, user: User, status: str) -> None:
    """Idempotent: education, license and placeholder documents (private volume) for a seeded therapist."""
    education, (ltype, body, number, issued, valid) = VERIFICATION[user.email]
    if db.scalar(select(TherapistEducation.id).where(TherapistEducation.therapist_id == profile.id).limit(1)) is None:
        db.add_all(TherapistEducation(therapist_id=profile.id, degree=d, institution=i, year=y) for d, i, y in education)
    if db.scalar(select(TherapistLicense.id).where(TherapistLicense.therapist_id == profile.id).limit(1)) is None:
        db.add(TherapistLicense(therapist_id=profile.id, license_type=ltype, registration_body=body,
                                registration_number=number, issue_year=issued, valid_until=date.fromisoformat(valid)))
    docs = db.scalars(select(VerificationDocument).where(VerificationDocument.owner_type == OWNER_TYPE,
                                                         VerificationDocument.owner_id == profile.id)).all()
    if not docs:
        for doc_type, title in (("degree_certificate", f"{education[0][0]} - sample certificate"),
                                ("registration_certificate", f"{body} - sample registration")):
            store_document(db, profile, doc_type, f"{doc_type.replace('_', '-')}.pdf", _placeholder_pdf(title))
    for doc in docs:  # repair after a volume reset
        path = upload_dir() / doc.storage_key
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_placeholder_pdf(f"{doc.doc_type} - sample document"))


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


MOOD_DAYS = 30


def seed_mood(db: Session, now: datetime, client: User, spec: dict) -> None:
    """30 days of mood/sleep for a client with history. Idempotent: skipped once the client has any entry.
    Mood follows the client's latest PHQ-9 loosely; the day-to-day wobble is deterministic."""
    if db.scalar(select(MoodCheckin.id).where(MoodCheckin.client_id == client.id).limit(1)) is not None:
        return
    latest = spec["phq9"][-1][1]
    base = max(1.5, min(4.5, 5.0 - latest / 7))
    for i in range(MOOD_DAYS):
        day = (now - timedelta(days=MOOD_DAYS - 1 - i)).date()
        if (i * 7 + client.id) % 11 == 0:
            continue  # a few quiet days with no entry
        wobble = ((i * 5 + client.id * 3) % 7 - 3) / 3
        trend = (i - MOOD_DAYS / 2) / MOOD_DAYS * (1 if spec["phq9"][-1][1] < spec["phq9"][0][1] else 0)
        mood = max(1, min(5, round(base + wobble * 0.8 + trend)))
        sleep = round(max(3.5, min(9.0, 5.0 + (mood - 2.5) * 0.7 + ((i * 3 + client.id) % 5 - 2) * 0.25)) * 2) / 2
        db.add(MoodCheckin(client_id=client.id, entry_date=day, mood=mood, sleep_hours=sleep,
                           created_at=now - timedelta(days=MOOD_DAYS - 1 - i), updated_at=now - timedelta(days=MOOD_DAYS - 1 - i)))


def seed_journeys(db: Session, now: datetime, users: dict[str, User]) -> None:
    exercises = {e.slug: e.id for e in db.scalars(select(Exercise))}
    for spec in JOURNEYS:
        if db.scalar(select(Journey.id).where(Journey.slug == spec["slug"])) is not None:
            continue
        journey = Journey(slug=spec["slug"], title_en=spec["title_en"], title_hi=spec["title_hi"])
        db.add(journey)
        db.flush()
        for pos, (week, slug, en, hi) in enumerate(spec["steps"]):
            db.add(JourneyStep(journey_id=journey.id, week=week, position=pos, exercise_id=exercises[slug], text_en=en, text_hi=hi))
        db.flush()
    spec = JOURNEY_ASSIGNMENT
    client = users[spec["client"]]
    key = f"seed:journey:{client.id}:{spec['slug']}"
    if db.scalar(select(JourneyAssignment.id).where(JourneyAssignment.client_id == client.id,
                                                    JourneyAssignment.idempotency_key == key)) is not None:
        return
    plan = db.scalar(select(CasePlan).where(CasePlan.client_id == client.id).order_by(CasePlan.id.desc()))
    if plan is None:
        return
    journey = db.scalar(select(Journey).where(Journey.slug == spec["slug"]))
    started = (now - timedelta(days=spec["started_days_ago"])).date()
    assignment = JourneyAssignment(journey_id=journey.id, client_id=client.id, therapist_user_id=plan.therapist_user_id,
                                   started_on=started, idempotency_key=key, created_at=now - timedelta(days=spec["started_days_ago"]))
    db.add(assignment)
    db.flush()
    for step in db.scalars(select(JourneyStep).where(JourneyStep.journey_id == journey.id, JourneyStep.week <= spec["done_weeks"])):
        db.add(JourneyStepProgress(assignment_id=assignment.id, step_id=step.id,
                                   completed_at=now - timedelta(days=spec["started_days_ago"] - step.week - step.position)))


def seed(db: Session, *, load_kb: bool = True, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    users = {email: _user(db, email, pw, role, name) for email, pw, role, name in LOGINS}
    practices = {p["slug"]: _practice(db, p, users[p["owner"]]) for p in PRACTICES}
    _setup_practice(db, now, users)
    profiles = {row[0]: _profile(db, users[row[0]], practices[row[1]], row) for row in THERAPISTS}
    pending = PENDING_THERAPIST
    _profile(db, users[pending[0]], practices[pending[1]], pending, status="submitted")
    if load_kb:
        db.commit()
        rag.load_kb(db)
    for idx, (email, spec) in enumerate(CASES.items()):
        if spec is not None:
            _seed_client(db, now, idx, users[email], users[spec["therapist"]], profiles[spec["therapist"]], spec)
    for email, spec in CASES.items():
        if spec is not None:
            seed_mood(db, now, users[email], spec)
    seed_journeys(db, now, users)
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
