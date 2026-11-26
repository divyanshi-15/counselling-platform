"""Create or refresh review accounts: one client, one verified therapist with rich fictional data, one practice owner
with a draft practice ready for the Launch flow. Idempotent; passwords come only from the environment.

    JUDGE_PASSWORD_CLIENT=... JUDGE_PASSWORD_THERAPIST=... JUDGE_PASSWORD_OWNER=... \
        python -m backend.scripts.create_judge_accounts

Needs a migrated database (exercises come from migrations). Safe to re-run: passwords are reset, the therapist stays
verified, availability is topped up, and clinical sample data is added only once.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import hash_password
from backend.app.db import SessionLocal
from backend.app.models import Practice, TherapistProfile, User
from backend.app.practice_setup import set_practice_status
from backend.scripts import seed
from backend.scripts.seed_data import (
    CASES,
    COMMON_PAGE,
    PRACTICE_DETAILS,
    PRACTICES,
    THERAPISTS,
    VERIFICATION,
)

MIN_LENGTH = 12
ENV = {"client": "JUDGE_PASSWORD_CLIENT", "therapist": "JUDGE_PASSWORD_THERAPIST", "owner": "JUDGE_PASSWORD_OWNER"}
EMAILS = {"client": "judge.client@saarthi-cares.com", "therapist": "judge.therapist@saarthi-cares.com",
          "owner": "judge.owner@saarthi-cares.com", "host": "judge.clinic@saarthi-cares.com",
          "companion": "judge.client2@saarthi-cares.com"}
CLINIC_SLUG, DRAFT_SLUG = "saarthi-review-clinic", "saarthi-review-practice"


def read_passwords(env: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ if env is None else env
    problems, out = [], {}
    for role, var in ENV.items():
        value = env.get(var, "")
        if not value:
            problems.append(f"{var} is not set")
        elif len(value) < MIN_LENGTH:
            problems.append(f"{var} must be at least {MIN_LENGTH} characters")
        out[role] = value
    if problems:
        raise SystemExit("Cannot create judge accounts:\n  " + "\n  ".join(problems))
    return out


def _user(db: Session, email: str, password: str, role: str, name: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, role=role, language="en", name=name, password_hash=hash_password(password))
        db.add(user)
    user.name, user.role, user.password_hash = name, role, hash_password(password)
    user.is_verified = role == "therapist"
    db.flush()
    return user


def _clinic(db: Session, host: User) -> Practice:
    """Published, verified practice that hosts the review therapist (a copy of the first seeded practice's shape)."""
    base = PRACTICES[0]
    practice = db.scalar(select(Practice).where(Practice.slug == CLINIC_SLUG))
    if practice is None:
        practice = Practice(slug=CLINIC_SLUG, name="Saarthi Review Clinic", owner_id=host.id, status="published", page_json="{}")
        db.add(practice)
    practice.owner_id = host.id
    practice.page_json = json.dumps(COMMON_PAGE | base["page"])
    practice.languages = base["page"]["languages"]
    for key, value in PRACTICE_DETAILS[base["slug"]].items():
        setattr(practice, key, value)
    set_practice_status(practice, "verified")
    db.flush()
    return practice


def _draft_practice(db: Session, owner: User) -> Practice:
    """A draft with no page yet, so the owner starts the Launch flow from a one-sentence description."""
    practice = db.scalar(select(Practice).where(Practice.slug == DRAFT_SLUG))
    if practice is None:
        practice = Practice(slug=DRAFT_SLUG, name="Saarthi Review Practice", owner_id=owner.id, status="draft", page_json="{}")
        db.add(practice)
        set_practice_status(practice, "draft")
    practice.owner_id = owner.id
    db.flush()
    return practice


def _therapist_profile(db: Session, user: User, practice: Practice) -> TherapistProfile:
    row = (user.email, practice.slug, *THERAPISTS[0][2:])
    VERIFICATION[user.email] = VERIFICATION[THERAPISTS[0][0]]
    try:
        return seed._profile(db, user, practice, row)
    finally:
        del VERIFICATION[user.email]


def create(db: Session, passwords: dict[str, str], now: datetime | None = None) -> dict[str, str]:
    now = now or datetime.now(timezone.utc)
    host = _user(db, EMAILS["host"], secrets.token_urlsafe(24), "practice_owner", "Review Clinic Admin")
    owner = _user(db, EMAILS["owner"], passwords["owner"], "practice_owner", "Aditi Rao")
    therapist = _user(db, EMAILS["therapist"], passwords["therapist"], "therapist", "Dr. Meera Iyer")
    client = _user(db, EMAILS["client"], passwords["client"], "client", "Rohan Mehta")
    companion = _user(db, EMAILS["companion"], secrets.token_urlsafe(24), "client", "Sana Qureshi")
    clinic = _clinic(db, host)
    _draft_practice(db, owner)
    profile = _therapist_profile(db, therapist, clinic)
    # Rich clinical data: the two fictional cases used in the product story, attached to this therapist.
    for idx, (person, source) in enumerate(((client, "client@example.com"), (companion, "client2@example.com"))):
        spec = CASES[source] | {"therapist": therapist.email}
        seed._seed_client(db, now, 40 + idx, person, therapist, profile, spec)
        seed.seed_mood(db, now, person, spec)
    seed.refresh_slots(db, [profile], now)
    db.commit()
    return {role: EMAILS[role] for role in ENV}


if __name__ == "__main__":
    pw = read_passwords()
    with SessionLocal() as session:
        accounts = create(session, pw)
    print("Judge accounts ready (passwords come from your environment):")
    for role, email in accounts.items():
        print(f"  {role:<10} {email}")
