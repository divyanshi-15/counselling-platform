from __future__ import annotations

from argon2 import PasswordHasher
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import User, UserRole

engine = create_engine(settings.database_url, future=True)


def seed() -> None:
    hasher = PasswordHasher()
    with Session(engine) as db:
        for email, password, role in [
            ("admin@example.com", "admin123", UserRole.admin),
            ("owner@example.com", "owner123", UserRole.practice_owner),
            ("therapist@example.com", "therapist123", UserRole.therapist),
            ("client@example.com", "client123", UserRole.client),
        ]:
            existing = db.query(User).filter(User.email == email.lower()).first()
            if not existing:
                db.add(
                    User(
                        email=email.lower(),
                        password_hash=hasher.hash(password),
                        role=role,
                        language="en",
                        name=email.split("@")[0],
                    )
                )
        db.commit()


if __name__ == "__main__":
    seed()
    print("Seed complete")
