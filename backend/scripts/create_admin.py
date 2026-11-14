"""Create an admin user: python -m backend.scripts.create_admin EMAIL PASSWORD. Only way (besides seed) to get an admin."""
from __future__ import annotations

import sys

from sqlalchemy import select

from backend.app.auth import hash_password
from backend.app.db import SessionLocal
from backend.app.models import User, UserRole


def create_admin(db, email: str, password: str) -> User:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    email = email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise ValueError("User already exists")
    user = User(email=email, password_hash=hash_password(password), role=UserRole.admin, language="en",
                name="Admin", is_verified=True)
    db.add(user)
    db.commit()
    return user


if __name__ == "__main__":
    if len(sys.argv) != 3 or not sys.argv[1] or not sys.argv[2]:
        sys.exit("usage: make create-admin EMAIL=... PASSWORD=...")
    with SessionLocal() as session:
        try:
            create_admin(session, sys.argv[1], sys.argv[2])
        except ValueError as exc:
            sys.exit(str(exc))
    print("Admin created.")
