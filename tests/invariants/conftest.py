"""Shared fixtures for the invariant suite (docs/ROADMAP.md, section 3)."""
from __future__ import annotations

import pytest
from invariant_support import USERS
from sqlalchemy import delete, select

from backend.app.auth import create_access_token
from backend.app.db import SessionLocal
from backend.app.models import Practice, User
from backend.scripts import seed as seed_mod


@pytest.fixture(scope="module")
def seeded_world():
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS])))
            db.execute(delete(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS)))
            db.commit()

    wipe()
    with SessionLocal() as db:
        seed_mod.seed(db, load_kb=False)
    yield
    wipe()


@pytest.fixture(scope="module")
def tokens(seeded_world) -> dict[str, dict[str, str]]:
    out = {}
    with SessionLocal() as db:
        for name, email in USERS.items():
            u = db.scalar(select(User).where(User.email == email))
            out[name] = {"Authorization": f"Bearer {create_access_token(u.email, u.role)}"}
    return out


@pytest.fixture(scope="module")
def ids(seeded_world) -> dict[str, int]:
    with SessionLocal() as db:
        return {name: db.scalar(select(User.id).where(User.email == email)) for name, email in USERS.items()}
