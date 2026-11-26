from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.agents.launch import draft_page, evaluate_claims_with_model, run_launch_agent
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import AgentRun, AuditLog, PendingAction, Practice, User


def _launch_input(tone: str = "warm and calm") -> dict[str, object]:
    return {
        "name": "North Star Care",
        "location": "Bengaluru",
        "languages": ["en", "hi"],
        "specialties": ["stress"],
        "approaches": ["CBT"],
        "fee_range": "2000-3000",
        "tone": tone,
        "session_type": "online",
    }


def test_launch_agent_revises_claims_before_returning_page() -> None:
    with (
        patch("backend.app.agents.launch._request_page_json", return_value=None),
        patch(
            "backend.app.agents.launch.evaluate_claims_with_model",
            return_value={"status": "ok", "passed": True, "reasons": []},
        ),
    ):
        result = run_launch_agent(_launch_input("guaranteed results"))

    assert result["status"] == "ok"
    assert "guaranteed" not in str(result["page"]).lower()
    assert [entry["tool"] for entry in result["agent_runs"]] == [
        "draft_page",
        "check_claims",
        "revise_page",
        "check_claims",
    ]
    assert [entry["step"] for entry in result["agent_runs"]] == [1, 2, 3, 4]


def test_claims_model_parses_markdown_wrapped_json(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("backend.app.agents.launch.httpx.post") as post:
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "content": [{"type": "text", "text": "```json\n{\"passed\": false, \"reasons\": [\"contains banned claim pattern\"]}\n```"}],
            "usage": {"input_tokens": 12, "output_tokens": 8},
        }

        result = evaluate_claims_with_model("This practice guarantees help in 4 sessions.")

    assert result["status"] == "ok"
    assert result["passed"] is False
    assert result["reasons"] == ["contains banned claim pattern"]


def test_draft_page_normalizes_string_expectations() -> None:
    raw = '{"tagline": "Calm support", "about": "Supportive care.", "services": [{"name": "Consultation", "description": "A first conversation."}], "faq": [{"question": "What happens first?", "answer": "We start with a careful conversation."}], "what_to_expect": "Clear next steps"}'
    with patch("backend.app.agents.launch._request_page_json", return_value=raw):
        page = draft_page(_launch_input())

    assert page["what_to_expect"] == ["Clear next steps"]
    assert page["services"][0]["title"] == "Consultation"


def test_launch_agent_never_exceeds_tool_call_limit() -> None:
    with (
        patch("backend.app.agents.launch._request_page_json", return_value=None),
        patch("backend.app.agents.launch.check_claims", return_value=(False, ["unsafe claim"], None)) as check,
        patch("backend.app.agents.launch.draft_page", wraps=__import__("backend.app.agents.launch", fromlist=["draft_page"]).draft_page) as draft,
        patch("backend.app.agents.launch.revise_page", wraps=__import__("backend.app.agents.launch", fromlist=["revise_page"]).revise_page) as revise,
    ):
        with pytest.raises(ValueError, match="max tool call limit"):
            run_launch_agent(_launch_input(), max_calls=8)

    assert draft.call_count + check.call_count + revise.call_count == 8


def test_launch_agent_rejects_nonpositive_tool_call_limit() -> None:
    with pytest.raises(ValueError, match="max_calls must be positive"):
        run_launch_agent(_launch_input(), max_calls=0)


def test_draft_retries_invalid_json_once_with_configured_token_limit() -> None:
    valid_page = json.dumps({
        "tagline": "Practical support for your next step",
        "about": "A collaborative counselling practice.",
        "services": [{"title": "Consultation", "description": "A first conversation."}],
        "faq": [{"question": "What should I expect?", "answer": "A collaborative conversation."}],
        "what_to_expect": ["Clear next steps"],
    })
    with patch(
        "backend.app.agents.launch._request_page_json",
        side_effect=["not JSON", valid_page],
    ) as request:
        page = draft_page(_launch_input(), max_tokens=96)

    assert page["tagline"] == "Practical support for your next step"
    assert request.call_count == 2
    assert all(call.kwargs["max_tokens"] == 96 for call in request.call_args_list)


def test_draft_surfaces_error_after_second_invalid_json_response() -> None:
    with patch(
        "backend.app.agents.launch._request_page_json",
        return_value="not JSON",
    ) as request:
        with pytest.raises(ValueError, match="invalid JSON after one retry"):
            draft_page(_launch_input())

    assert request.call_count == 2


def _register_user(client: TestClient, role: str) -> tuple[str, int]:
    email = f"{role}-{uuid4().hex}@example.com"
    registered = client.post(
        "/auth/register",
        json={"email": email, "password": "secret1234", "role": "client" if role == "admin" else role, "language": "en", "name": role.title()},
    )
    assert registered.status_code == 200, registered.text
    if role == "admin":  # admins cannot self-register; promote directly in the DB
        with SessionLocal() as db:
            db.query(User).filter(User.email == email).update({"role": "admin", "is_verified": True})
            db.commit()
    login = client.post("/auth/login", json={"email": email, "password": "secret1234"})
    assert login.status_code == 200, login.text
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['token']}"})
    assert user.status_code == 200, user.text
    client.cookies.clear()
    return login.json()["token"], user.json()["id"]


def _create_practice(owner_id: int) -> Practice:
    with SessionLocal() as db:
        practice = Practice(
            name="Launch Test Practice",
            slug=f"launch-test-{uuid4().hex}",
            owner_id=owner_id,
            status="draft",
            verified=False,
            page_json="{}",
        )
        db.add(practice)
        db.commit()
        db.refresh(practice)
        return practice


def test_agent_creates_one_action_and_owner_approval_publishes_once() -> None:
    with TestClient(app) as client:
        token, owner_id = _register_user(client, "practice_owner")
        practice = _create_practice(owner_id)
        with (
            patch("backend.app.agents.launch._request_page_json", return_value=None),
            patch(
                "backend.app.agents.launch.evaluate_claims_with_model",
                return_value={"status": "ok", "passed": True, "reasons": []},
            ),
        ):
            draft = client.post(
                f"/practices/{practice.id}/draft-with-agent",
                json=_launch_input(),
                headers={"Authorization": f"Bearer {token}"},
            )

        assert draft.status_code == 200, draft.text
        assert draft.json()["status"] == "draft"
        action_data = draft.json()["pending_action"]
        assert action_data["status"] == "pending"
        with SessionLocal() as db:
            actions = db.query(PendingAction).filter(PendingAction.practice_id == practice.id).all()
            runs = db.query(AgentRun).filter(AgentRun.practice_id == practice.id).all()
            assert len(actions) == 1
            assert actions[0].type == "publish_page"
            assert actions[0].idempotency_key
            assert actions[0].payload["draft"] == draft.json()["page"]
            assert len(runs) == 2

        headers = {"Authorization": f"Bearer {token}"}
        agent_runs = client.get(f"/practices/{practice.id}/agent-runs", headers=headers)
        assert agent_runs.status_code == 200
        assert len(agent_runs.json()["items"]) == 2
        approved = client.post(
            f"/pending-actions/{action_data['id']}/approve",
            headers=headers | {"Idempotency-Key": action_data["idempotency_key"]},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        with SessionLocal() as db:
            saved_page = db.query(Practice).filter(Practice.id == practice.id).first().page_json
            action = db.query(PendingAction).filter(PendingAction.id == action_data["id"]).first()
            decided_at = action.decided_at
            assert action.decided_by == owner_id
            assert decided_at is not None

        repeated = client.post(
            f"/pending-actions/{action_data['id']}/approve",
            headers=headers | {"Idempotency-Key": action_data["idempotency_key"]},
        )
        assert repeated.status_code == 200
        assert repeated.json()["status"] == "approved"
        assert repeated.json() == approved.json()
        with SessionLocal() as db:
            saved = db.query(Practice).filter(Practice.id == practice.id).first()
            assert saved.status == "draft"  # approved, but an unverified practice is never published
            assert saved.page_json == saved_page
            action = db.query(PendingAction).filter(PendingAction.id == action_data["id"]).first()
            assert action.decided_at == decided_at
            assert db.query(AuditLog).filter(
                AuditLog.action == "pending_action.approve",
                AuditLog.entity_id == action.id,
            ).count() == 2
        assert client.post(f"/practices/{practice.id}/publish", headers=headers).status_code == 404


def test_agent_runs_endpoint_is_limited_to_owner_and_admin() -> None:
    with TestClient(app) as client:
        owner_token, owner_id = _register_user(client, "practice_owner")
        other_token, _ = _register_user(client, "practice_owner")
        admin_token, _ = _register_user(client, "admin")
        practice = _create_practice(owner_id)
        with (
            patch("backend.app.agents.launch._request_page_json", return_value=None),
            patch("backend.app.agents.launch.evaluate_claims_with_model", return_value={"status": "ok", "passed": True, "reasons": []}),
        ):
            response = client.post(
                f"/practices/{practice.id}/draft-with-agent",
                json=_launch_input(),
                headers={"Authorization": f"Bearer {owner_token}"},
            )
        assert response.status_code == 200

        owner_runs = client.get(f"/practices/{practice.id}/agent-runs", headers={"Authorization": f"Bearer {owner_token}"})
        admin_runs = client.get(f"/practices/{practice.id}/agent-runs", headers={"Authorization": f"Bearer {admin_token}"})
        other_runs = client.get(f"/practices/{practice.id}/agent-runs", headers={"Authorization": f"Bearer {other_token}"})
        assert owner_runs.status_code == 200 and owner_runs.json()["items"]
        assert admin_runs.status_code == 200 and admin_runs.json()["items"]
        assert other_runs.status_code == 403
        owner_actions = client.get("/pending-actions", headers={"Authorization": f"Bearer {owner_token}"})
        other_actions = client.get("/pending-actions", headers={"Authorization": f"Bearer {other_token}"})
        assert [item["practice_id"] for item in owner_actions.json()["items"]] == [practice.id]
        assert other_actions.json()["items"] == []


def test_non_owner_cannot_approve_pending_action() -> None:
    with TestClient(app) as client:
        owner_token, owner_id = _register_user(client, "practice_owner")
        other_token, _ = _register_user(client, "practice_owner")
        practice = _create_practice(owner_id)
        with (
            patch("backend.app.agents.launch._request_page_json", return_value=None),
            patch("backend.app.agents.launch.evaluate_claims_with_model", return_value={"status": "ok", "passed": True, "reasons": []}),
        ):
            draft = client.post(
                f"/practices/{practice.id}/draft-with-agent",
                json=_launch_input(),
                headers={"Authorization": f"Bearer {owner_token}"},
            )
        assert draft.status_code == 200, draft.text
        action = draft.json()["pending_action"]
        response = client.post(
            f"/pending-actions/{action['id']}/approve",
            headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": action["idempotency_key"]},
        )
        assert response.status_code == 403


def test_owner_can_reject_pending_action_and_rejection_is_audited() -> None:
    with TestClient(app) as client:
        owner_token, owner_id = _register_user(client, "practice_owner")
        practice = _create_practice(owner_id)
        with (
            patch("backend.app.agents.launch._request_page_json", return_value=None),
            patch("backend.app.agents.launch.evaluate_claims_with_model", return_value={"status": "ok", "passed": True, "reasons": []}),
        ):
            draft = client.post(
                f"/practices/{practice.id}/draft-with-agent",
                json=_launch_input(),
                headers={"Authorization": f"Bearer {owner_token}"},
            )
        assert draft.status_code == 200, draft.text
        action = draft.json()["pending_action"]
        rejected = client.post(
            f"/pending-actions/{action['id']}/reject",
            headers={"Authorization": f"Bearer {owner_token}", "Idempotency-Key": action["idempotency_key"]},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        with SessionLocal() as db:
            saved = db.query(Practice).filter(Practice.id == practice.id).first()
            assert saved.status == "draft"
            assert db.query(AuditLog).filter(
                AuditLog.action == "pending_action.reject",
                AuditLog.entity_id == action["id"],
            ).count() == 1


def test_admin_verification_does_not_publish_or_change_page_and_is_audited() -> None:
    with TestClient(app) as client:
        admin_token, admin_id = _register_user(client, "admin")
        practice = _create_practice(admin_id)
        original_page = practice.page_json
        with SessionLocal() as db:
            db.query(Practice).filter(Practice.id == practice.id).update({"verification_status": "submitted"})
            db.commit()
        response = client.post(
            f"/admin/practices/{practice.id}/review",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": "verified"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "verified"
        assert response.json()["verified"] is True
        with SessionLocal() as db:
            updated = db.query(Practice).filter(Practice.id == practice.id).first()
            assert updated.status == "draft"
            assert updated.page_json == original_page
            audit = db.query(AuditLog).filter(
                AuditLog.action == "practice.review",
                AuditLog.entity_id == practice.id,
            ).one()
            assert audit.actor_id == admin_id


def test_other_user_cannot_run_practice_launch_agent() -> None:
    with TestClient(app) as client:
        owner_token, owner_id = _register_user(client, "practice_owner")
        other_token, _ = _register_user(client, "client")
        practice = _create_practice(owner_id)

        with patch("backend.app.main.run_launch_agent") as run_agent:
            response = client.post(
                f"/practices/{practice.id}/draft-with-agent",
                json=_launch_input(),
                headers={"Authorization": f"Bearer {other_token}"},
            )

        assert response.status_code == 403
        run_agent.assert_not_called()