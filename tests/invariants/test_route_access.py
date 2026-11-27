"""Invariant: server-side access control. Every route is classified from its dependency tree, and any route that is
not covered by a role guard, a therapist-of-client guard, or an explicit allowlist entry fails the build. A new endpoint
therefore cannot ship without declaring how it is protected, and each declared guard is exercised here."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from invariant_support import iter_api_routes

from backend.app import auth
from backend.app.main import app

# Intentionally unauthenticated. Anything new here needs a reason in review.
PUBLIC = {
    ("GET", "/"), ("GET", "/health"), ("GET", "/config"),
    ("POST", "/auth/login"), ("POST", "/auth/logout"), ("POST", "/auth/register"), ("POST", "/auth/demo-login"),
    ("POST", "/contact"), ("POST", "/practices/contact"),
    ("POST", "/demo/ai-output-validator"), ("POST", "/demo/prompt-guard"), ("POST", "/demo/safety-check"),
    ("GET", "/p/{slug}"), ("GET", "/practices/public"),
    ("GET", "/therapists/public"), ("GET", "/therapists/public/{therapist_id}"),
    ("GET", "/therapists/{therapist_id}/availability"),
}

# Authenticated, with the ownership or role decision made inside the handler. Each is covered by the named tests;
# the generic test below still proves they reject anonymous callers.
HANDLER_CHECKED = {
    ("GET", "/auth/me"): "own record only",
    ("GET", "/bookings/{booking_id}/intake-form"): "tests/test_therapist_booking_intake.py",
    ("GET", "/bookings/{booking_id}/intake-response"): "tests/test_therapist_booking_intake.py",
    ("PUT", "/bookings/{booking_id}/session-notes"): "tests/test_copilot.py",
    ("GET", "/bookings/{booking_id}/session-notes"): "tests/test_copilot.py",
    ("GET", "/pending-actions"): "tests/test_braindump.py (owner gets empty list)",
    ("POST", "/pending-actions/{action_id}/approve"): "tests/test_braindump.py, tests/test_copilot.py",
    ("PUT", "/pending-actions/{action_id}/draft"): "tests/test_braindump.py",
    ("POST", "/pending-actions/{action_id}/reject"): "tests/test_braindump.py",
    ("GET", "/practices"): "tests/test_practice_api.py",
    ("GET", "/practices/{practice_id}/agent-runs"): "tests/test_practice_api.py",
    ("POST", "/practices/{practice_id}/draft-with-agent"): "tests/test_practice_launch_agent.py",
    ("GET", "/verification-documents/{doc_id}/download"): "tests/test_verification.py",
}

ALL_ROLES = ("admin", "practice_owner", "therapist", "client")


def classify(route) -> tuple[str, tuple[str, ...]]:
    roles: set[str] = set()
    kinds: set[str] = set()

    def walk(dep):
        for d in dep.dependencies:
            call = d.call
            if getattr(call, "__qualname__", "").startswith("require_roles.<locals>"):
                cells = {n: v.cell_contents for n, v in zip(call.__code__.co_freevars, call.__closure__)}
                roles.update(getattr(r, "value", r) for r in cells["roles"])
                kinds.add("roles")
            elif call is auth.get_current_user:
                kinds.add("authenticated")
            elif call is auth.require_therapist_of_client:
                kinds.add("therapist_of_client")
            walk(d)

    walk(route.dependant)
    if "roles" in kinds:
        return "roles", tuple(sorted(roles))
    if "therapist_of_client" in kinds:
        return "therapist_of_client", ()
    if "authenticated" in kinds:
        return "handler_checked", ()
    return "public", ()


ROUTES = sorted(
    {(m, r.path): classify(r) for r in iter_api_routes() for m in r.methods if m not in {"HEAD", "OPTIONS"}}.items()
)
client = TestClient(app)


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def _call(method: str, path: str, headers: dict[str, str] | None = None):
    return client.request(method, _url(path), headers=headers or {}, json={} if method in {"POST", "PUT", "PATCH"} else None)


def test_registry_has_no_stale_or_unclassified_routes() -> None:
    declared = {key for key, (kind, _) in ROUTES}
    public = {key for key, (kind, _) in ROUTES if kind == "public"}
    unclassified = public - PUBLIC
    assert not unclassified, f"routes with no auth dependency must be listed in PUBLIC with a reason: {sorted(unclassified)}"
    handler = {key for key, (kind, _) in ROUTES if kind == "handler_checked"}
    assert not handler - set(HANDLER_CHECKED), f"authenticated-only routes must be in HANDLER_CHECKED: {sorted(handler - set(HANDLER_CHECKED))}"
    stale = (PUBLIC | set(HANDLER_CHECKED)) - declared
    assert not stale, f"allowlist entries for routes that no longer exist: {sorted(stale)}"


GUARDED = [(key, kind, roles) for key, (kind, roles) in ROUTES if kind != "public"]


@pytest.mark.parametrize("key,kind,roles", GUARDED, ids=[f"{k[0]} {k[1]}" for k, _, _ in GUARDED])
def test_anonymous_is_rejected(key, kind, roles) -> None:
    assert _call(*key).status_code == 401


ROLE_GUARDED = [(key, roles) for key, kind, roles in GUARDED if kind == "roles"]


@pytest.mark.parametrize("key,roles", ROLE_GUARDED, ids=[f"{k[0]} {k[1]}" for k, _ in ROLE_GUARDED])
def test_other_roles_are_denied(key, roles, tokens) -> None:
    for role in set(ALL_ROLES) - set(roles):
        resp = _call(*key, headers=tokens[role])
        assert resp.status_code == 403, f"{role} reached {key}: {resp.status_code}"


CLINICAL = [key for key, kind, _ in GUARDED if kind == "therapist_of_client"]


@pytest.mark.parametrize("key", CLINICAL, ids=[f"{k[0]} {k[1]}" for k in CLINICAL])
def test_clinical_routes_only_for_the_clients_therapist(key, tokens, ids) -> None:
    method, path = key
    url = path.replace("{client_id}", str(ids["client"]))
    url = re.sub(r"\{[^}]+\}", "1", url)
    body = {} if method in {"POST", "PUT", "PATCH"} else None
    # owner, admin, another client, the client themself, and a therapist with no booking or plan with this client.
    for who in ("practice_owner", "admin", "other_client", "client", "other_therapist"):
        resp = client.request(method, url, headers=tokens[who], json=body)
        assert resp.status_code == 403, f"{who} reached {key}: {resp.status_code}"
