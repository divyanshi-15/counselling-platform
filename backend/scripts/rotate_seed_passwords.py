"""Rotate every account still using a seeded default password.

Usage: python -m backend.scripts.rotate_seed_passwords > seed-credentials.txt
Idempotent: only users whose password still matches a seeded default are changed, so a second
run rotates nothing. New credentials go to stdout (email, role, password); progress to stderr.
"""
from __future__ import annotations

import secrets
import sys

from sqlalchemy import select

from backend.app.auth import hash_password, verify_password
from backend.app.db import SessionLocal
from backend.app.models import User
from backend.scripts.seed_data import LOGINS


def rotate(db) -> list[tuple[str, str, str]]:
    defaults = {password for _, password, _, _ in LOGINS}
    rotated: list[tuple[str, str, str]] = []
    for user in db.scalars(select(User).order_by(User.id)):
        if any(verify_password(p, user.password_hash) for p in defaults):
            new = secrets.token_urlsafe(24)
            user.password_hash = hash_password(new)
            rotated.append((user.email, user.role, new))
    db.commit()
    return rotated


if __name__ == "__main__":
    with SessionLocal() as session:
        rows = rotate(session)
    for email, role, password in rows:
        print(f"{email}\t{role}\t{password}")
    print(f"rotated {len(rows)} account(s)", file=sys.stderr)
