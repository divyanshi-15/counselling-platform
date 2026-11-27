"""Helpers shared by the invariant tests."""
from __future__ import annotations

from fastapi.routing import APIRoute

from backend.app.main import app

# One seeded user per role, plus an unrelated therapist (different practice) and a second client.
USERS = {
    "admin": "admin@example.com",
    "practice_owner": "owner@example.com",
    "therapist": "therapist@example.com",          # Calm Minds; treats client Alpha
    "other_therapist": "therapist3@example.com",   # Harbour; has no relationship with Alpha
    "client": "client@example.com",                # Alpha
    "other_client": "client2@example.com",         # Beta
}


def iter_api_routes(routes=None):
    """All APIRoutes, including those wrapped by include_router in this FastAPI version."""
    for r in routes if routes is not None else app.routes:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from iter_api_routes(r.original_router.routes)
