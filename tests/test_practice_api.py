from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import Practice, User, UserRole


def _seed_user(email: str, role: str = UserRole.practice_owner, password: str = "password123") -> User:
    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return existing
        user = User(
            email=email,
            password_hash="demo-hash",
            role=role,
            language="en",
            name="Demo User",
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def test_public_practice_list_excludes_unverified_and_draft_entries() -> None:
    owner = _seed_user("public-practice-owner@example.com")
    with SessionLocal() as db:
        db.query(Practice).delete()
        db.add_all(
            [
                Practice(
                    name="Bright Path",
                    slug="bright-path",
                    owner_id=owner.id,
                    status="published",
                    verified=True,
                    page_json='{"tagline": "Calm support for anxious adults", "language": "en", "specialty": "anxiety", "approach": "CBT", "fee": 2200, "session_type": "online"}',
                ),
                Practice(
                    name="Hidden Clinic",
                    slug="hidden-clinic",
                    owner_id=owner.id,
                    status="draft",
                    verified=True,
                    page_json='{"tagline": "Draft clinic", "language": "en", "specialty": "depression"}',
                ),
                Practice(
                    name="Unverified Clinic",
                    slug="unverified-clinic",
                    owner_id=owner.id,
                    status="published",
                    verified=False,
                    page_json='{"tagline": "Hidden"}',
                ),
            ]
        )
        db.commit()

    with TestClient(app) as client:
        response = client.get("/practices/public")
        assert response.status_code == 200
        payload = response.json()
        items = payload["items"]
        assert len(items) == 1
        assert items[0]["slug"] == "bright-path"


def test_practice_owner_can_create_draft_and_publish() -> None:
    email = f"owner-demo-{uuid4().hex}@example.com"
    with TestClient(app) as client:
        created = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "secret1234",
                "role": "practice_owner",
                "language": "en",
                "name": "Owner Demo",
            },
        )
        assert created.status_code == 200

        login_response = client.post(
            "/auth/login",
            json={"email": email, "password": "secret1234"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]

        draft = client.post(
            "/practices/draft",
            json={
                "name": "North Star Care",
                "location": "Bengaluru",
                "languages": ["en", "kn"],
                "specialties": ["anxiety", "stress"],
                "approaches": ["CBT"],
                "fee_range": "2000-3000",
                "tone": "warm and calm",
                "session_type": "online",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert draft.status_code == 200
        payload = draft.json()
        assert payload["status"] == "draft"
        assert payload["page"]["tagline"]

        actions = client.get("/pending-actions", headers={"Authorization": f"Bearer {token}"})
        action = next(item for item in actions.json()["items"] if item["practice_id"] == payload["id"])
        approved = client.post(
            f"/pending-actions/{action['id']}/approve",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": action["idempotency_key"]},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"


def test_claims_check_rejects_bait_prompts() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/practices/draft",
            json={
                "name": "Guaranteed Results Clinic",
                "location": "Bengaluru",
                "languages": ["en"],
                "specialties": ["stress"],
                "approaches": ["CBT"],
                "fee_range": "2000-3000",
                "tone": "guaranteed results and 100% improvement",
                "session_type": "online",
            },
            headers={"Authorization": "Bearer invalid"},
        )
        assert response.status_code == 401
