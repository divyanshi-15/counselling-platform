"""Idempotent demo seed. Synthetic, obviously fictional data only.

    python -m backend.scripts.seed            # seed (+ load KB)
    python -m backend.scripts.seed --check    # also print KB retrieval margins for the plateau client's notes
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app import rag
from backend.app.auth import hash_password
from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.models import (Assessment, Assignment, AvailabilitySlot, Booking, CasePlan, Checkin, Exercise,
                                IntakeForm, IntakeResponse, PendingAction, Practice, TherapistProfile, TherapySession,
                                User, UserRole)

LOGINS = [  # (email, password, role, name)
    ("admin@example.com", "admin123", UserRole.admin, "Demo Admin"),
    ("owner@example.com", "owner123", UserRole.practice_owner, "Demo Owner One"),
    ("owner2@example.com", "owner123", UserRole.practice_owner, "Demo Owner Two"),
    ("therapist@example.com", "therapist123", UserRole.therapist, "Dr Demo Therapist One"),
    ("therapist2@example.com", "therapist123", UserRole.therapist, "Dr Demo Therapist Two"),
    ("therapist3@example.com", "therapist123", UserRole.therapist, "Dr Demo Therapist Three"),
    ("client@example.com", "client123", UserRole.client, "Client Alpha Demo"),
    ("client2@example.com", "client123", UserRole.client, "Client Beta Demo"),
    ("client3@example.com", "client123", UserRole.client, "Client Gamma Demo"),
    ("client4@example.com", "client123", UserRole.client, "Client Delta Demo"),
]

PAGE = {
    "banner": "Demo: use fictional information only.",
    "tagline": "Calm, practical support for sleep and stress in Bengaluru.",
    "about": "Demo Calm Minds Practice offers warm, grounded skill-building support (fictional practice).",
    "services": [{"title": "Initial consultation", "description": "A first conversation to understand your needs."},
                 {"title": "Supportive sessions", "description": "Structured sessions informed by CBT."}],
    "faq": [{"question": "Is this online?", "answer": "Sessions are held online."}],
    "what_to_expect": ["Clear goals and a collaborative plan", "Simple next steps between sessions"],
    "location": "Bengaluru", "languages": ["en", "hi", "kn"], "specialties": ["sleep", "stress"],
    "approaches": ["CBT", "CBT-I"], "fee_range": "INR 1500-2500", "session_type": "online",
}

INTAKE_FIELDS = [{"id": "main_concern", "label": "What brings you here?", "required": True},
                 {"id": "sleep_hours", "label": "Typical hours of sleep"},
                 {"id": "goals", "label": "What would you like to change?"}]

# client email -> case spec. days_ago values are relative to "now" so the 14-day window always has data.
CASES = {
    "client@example.com": {  # plateau, low homework, one goal untouched; racing thoughts at night
        "therapist": "therapist@example.com", "approach": "CBT-I", "future_hours": 3,
        "phq9": [(20, 14), (13, 15), (6, 14), (0, 15)], "gad7": [(20, 13), (13, 13), (6, 14), (0, 13)],
        "goals": [{"id": "g1", "text": "Reduce racing thoughts at bedtime"},
                  {"id": "g2", "text": "Reconnect with weekend football friends"}],
        "formulation": "Evening worry and a busy mind keep the client alert at bedtime, which shortens sleep and lowers "
                       "daytime energy. Working hypothesis, to be reviewed each session.",
        "intake": {"main_concern": "My thoughts race at night and I am exhausted during the day.",
                   "sleep_hours": "About 5 hours a night", "goals": "Fall asleep faster and feel less tired"},
        "notes": [
            (21, "Client described racing thoughts at night that begin as soon as the lights are off. The mind replays "
                 "the day's conversations and plans tomorrow's tasks. It takes about two hours to fall asleep on most "
                 "nights. Sleeps around five hours and feels foggy in the afternoon. Agreed to keep a simple sleep diary."),
            (14, "Sleep diary shows bedtime between eleven and one. Client lies awake with thoughts going round and round "
                 "about work deadlines and checks the phone in bed. We discussed a worry time earlier in the evening and "
                 "writing worries down before bed. Homework: one thought record this week."),
            (7, "Only one thought record completed. Client says evenings are busy and thoughts still race at night. "
                "Talked about a wind-down hour without screens. Client feels discouraged about slow progress. Plan to try "
                "a ten minute worry postponement slot at seven in the evening."),
            (2, "Racing thoughts continue most nights; last night's thoughts were about an upcoming presentation. Client "
                "skipped the worry slot on four evenings. Energy is low and mood is flat. Agreed to simplify homework to "
                "one short exercise and to look at what makes the evening routine hard to keep."),
        ],
        "assignments": [(12, "thought_record", False), (9, "worry_postponement", True),
                        (6, "thought_record", False), (3, "worry_postponement", False)],
    },
    "client2@example.com": {  # improving; homework done
        "therapist": "therapist@example.com", "approach": "CBT", "future_hours": 5,
        "phq9": [(20, 16), (13, 13), (6, 10), (0, 8)], "gad7": [(20, 12), (13, 10), (6, 8), (0, 7)],
        "goals": [{"id": "g1", "text": "Use breathing exercise before exams"},
                  {"id": "g2", "text": "Plan one social activity each week"}],
        "formulation": "Exam pressure raises tension; avoiding social plans reduces support. Working hypothesis.",
        "intake": {"main_concern": "Exam stress and feeling tense before tests.", "sleep_hours": "About 7 hours a night",
                   "goals": "Feel calmer before exams"},
        "notes": [(14, "Client feels tense before exams. Practised slow breathing together and planned a social activity."),
                  (7, "Breathing exercise helped before the mock exams. Client met a classmate for a social activity."),
                  (1, "Exams went better than expected. Client keeps using breathing and planned another social activity.")],
        "assignments": [(10, "thought_record", True), (4, "worry_postponement", True)],
    },
    "client3@example.com": {
        "therapist": "therapist2@example.com", "approach": "CBT", "future_hours": 8,
        "phq9": [(20, 11), (13, 9), (6, 7), (0, 5)], "gad7": [(20, 8), (13, 6), (6, 5), (0, 4)],
        "goals": [{"id": "g1", "text": "Notice and name unhelpful thoughts"},
                  {"id": "g2", "text": "Spend time on valued activities"}],
        "formulation": "Work pressure and self-critical thoughts reduce time for valued activities. Working hypothesis.",
        "intake": {"main_concern": "Work pressure and a harsh inner critic.", "sleep_hours": "About 6 hours a night",
                   "goals": "Feel more settled at work"},
        "notes": [(14, "Client is learning to notice unhelpful thoughts about work performance."),
                  (7, "Named several unhelpful thoughts this week. Client booked time for a valued activity, painting."),
                  (1, "Client noticed fewer unhelpful thoughts and spent two evenings on valued activities.")],
        "assignments": [],
    },
    "client4@example.com": {
        "therapist": "therapist3@example.com", "approach": "CBT", "future_hours": 10,
        "phq9": [(20, 9), (13, 8), (6, 6), (0, 4)], "gad7": [(20, 7), (13, 6), (6, 4), (0, 3)],
        "goals": [{"id": "g1", "text": "Schedule one pleasant activity daily"},
                  {"id": "g2", "text": "Walk outside three times weekly"}],
        "formulation": "Fewer enjoyable plans over recent weeks; small scheduled steps help rebuild a daily rhythm. Working hypothesis.",
        "intake": {"main_concern": "Low energy and less interest in usual hobbies.", "sleep_hours": "About 8 hours a night",
                   "goals": "Return to my usual hobbies and weekly plans"},
        "notes": [(14, "Client scheduled one pleasant activity most days and walked outside twice."),
                  (7, "Pleasant activity each day is going well. Walk outside three times this week."),
                  (1, "Energy is better. Client keeps a pleasant activity plan and walks outside regularly.")],
        "assignments": [],
    },
}


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
                    is_verified=role in (UserRole.admin, UserRole.therapist))
        db.add(user)
        db.flush()
    return user


def _practice(db: Session, slug: str, name: str, owner: User, published: bool) -> Practice:
    practice = db.scalar(select(Practice).where(Practice.slug == slug))
    if practice is None:
        practice = Practice(slug=slug, name=name, owner_id=owner.id, status="published" if published else "draft",
                            verified=published, page_json=json.dumps(PAGE) if published else "{}")
        db.add(practice)
        db.flush()
    return practice


def _profile(db: Session, user: User, practice: Practice, bio: str, approaches: list[str], languages: list[str],
             fee: int, verified: bool) -> TherapistProfile:
    profile = db.scalar(select(TherapistProfile).where(TherapistProfile.user_id == user.id))
    if profile is None:
        profile = TherapistProfile(user_id=user.id, practice_id=practice.id, bio=bio, approaches=approaches,
                                   languages=languages, fee=fee, verified=verified)
        db.add(profile)
        db.flush()
    if db.scalar(select(IntakeForm.id).where(IntakeForm.therapist_id == profile.id)) is None:
        db.add(IntakeForm(therapist_id=profile.id, fields_json=INTAKE_FIELDS))
    return profile


def _slot(db: Session, profile: TherapistProfile, start: datetime) -> AvailabilitySlot:
    slot = AvailabilitySlot(therapist_id=profile.id, starts_at=start, ends_at=start + timedelta(minutes=50))
    db.add(slot)
    db.flush()
    return slot


def _seed_client(db: Session, now: datetime, idx: int, client: User, therapist: User, profile: TherapistProfile,
                 spec: dict) -> None:
    if db.scalar(select(Booking.id).where(Booking.client_id == client.id).limit(1)) is not None:
        return  # already seeded; reruns never duplicate
    base = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=idx)  # idx keeps slots unique per therapist
    for n, (days_ago, notes) in enumerate(spec["notes"]):
        start = base - timedelta(days=days_ago)
        booking = Booking(client_id=client.id, availability_slot_id=_slot(db, profile, start).id)
        db.add(booking)
        db.flush()
        if n == 0:
            db.add(IntakeResponse(booking_id=booking.id, client_id=client.id, answers_json=spec["intake"]))
        session = TherapySession(booking_id=booking.id, client_id=client.id, therapist_user_id=therapist.id,
                                 note_source="typed", raw_notes=notes, updated_at=start + timedelta(minutes=50))
        db.add(session)
        db.flush()
        rag.index_session_notes(db, therapist, client.id, session.id, notes)
    future = Booking(client_id=client.id,
                     availability_slot_id=_slot(db, profile, base + timedelta(hours=spec["future_hours"])).id)
    db.add(future)
    for kind, key, n in (("PHQ9", "phq9", 9), ("GAD7", "gad7", 7)):
        for days_ago, total in spec[key]:
            db.add(Assessment(client_id=client.id, recorded_by=therapist.id, type=kind, item_scores=_items(total, n),
                              total=total, taken_at=now - timedelta(days=days_ago, minutes=idx)))
    db.add(CasePlan(client_id=client.id, therapist_user_id=therapist.id, version=1, approach=spec["approach"],
                    formulation_text=spec["formulation"], goals_json=spec["goals"],
                    approved_at=now - timedelta(days=22), created_at=now - timedelta(days=22)))
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


def seed(db: Session, *, load_kb: bool = True) -> None:
    now = datetime.now(timezone.utc)
    users = {email: _user(db, email, pw, role, name) for email, pw, role, name in LOGINS}
    p1 = _practice(db, "demo-calm-minds", "Demo Calm Minds Practice", users["owner@example.com"], True)
    p2 = _practice(db, "demo-harbour-counselling", "Demo Harbour Counselling (draft)", users["owner2@example.com"], False)
    profiles = {
        "therapist@example.com": _profile(db, users["therapist@example.com"], p1, "Fictional CBT-I therapist.",
                                          ["CBT", "CBT-I"], ["en", "hi"], 1800, True),
        "therapist2@example.com": _profile(db, users["therapist2@example.com"], p1, "Fictional CBT therapist.",
                                           ["CBT"], ["en", "kn"], 1500, True),
        "therapist3@example.com": _profile(db, users["therapist3@example.com"], p2, "Fictional therapist, not yet verified.",
                                           ["CBT"], ["en"], 1200, False),
    }
    if load_kb:
        db.commit()
        rag.load_kb(db)
    for idx, (email, spec) in enumerate(CASES.items()):
        _seed_client(db, now, idx, users[email], users[spec["therapist"]], profiles[spec["therapist"]], spec)
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
    flagged = [t for c in CASES.values() for t in [n for _, n in c["notes"]] + list(c["intake"].values())
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
