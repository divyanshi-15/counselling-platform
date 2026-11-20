from __future__ import annotations

import pytest
from sqlalchemy import delete, func, select

from backend.app.auth import verify_password
from backend.app.db import SessionLocal
from backend.app.models import Booking, Practice, TherapistProfile, User
from backend.scripts import create_judge_accounts as judge

PW = {"client": "client-pass-1234", "therapist": "therapist-pass-1234", "owner": "owner-pass-12345"}


def _wipe():
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email.in_(judge.EMAILS.values())))
        db.execute(delete(Practice).where(Practice.slug.in_([judge.CLINIC_SLUG, judge.DRAFT_SLUG])))
        db.commit()


@pytest.fixture
def clean():
    _wipe()
    yield
    _wipe()


def test_missing_or_short_passwords_exit():
    with pytest.raises(SystemExit) as e:
        judge.read_passwords({"JUDGE_PASSWORD_CLIENT": "short"})
    msg = str(e.value)
    assert "JUDGE_PASSWORD_CLIENT must be at least 12" in msg and "JUDGE_PASSWORD_OWNER is not set" in msg


def test_create_is_idempotent_and_sets_up_roles(clean):
    for _ in range(2):
        with SessionLocal() as db:
            judge.create(db, PW)
    with SessionLocal() as db:
        users = {r: db.scalar(select(User).where(User.email == judge.EMAILS[r])) for r in PW}
        assert all(verify_password(PW[r], users[r].password_hash) for r in PW)
        assert users["therapist"].is_verified
        profile = db.scalar(select(TherapistProfile).where(TherapistProfile.user_id == users["therapist"].id))
        assert profile.verification_status == "verified"
        draft = db.scalar(select(Practice).where(Practice.slug == judge.DRAFT_SLUG))
        assert draft.owner_id == users["owner"].id and draft.status == "draft" and not draft.verified
        n = db.scalar(select(func.count(Booking.id)).where(Booking.client_id == users["client"].id))
        assert n > 3  # past sessions plus one upcoming, not duplicated on rerun
