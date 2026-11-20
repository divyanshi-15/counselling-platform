from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app.auth import create_access_token, hash_password
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import AgentRun, AuditLog, PendingAction, Practice, User

client = TestClient(app)
NAMES = ["northstar.com", "northstarcare.com", "northstar.in", "northstarcounselling.in", "northstar.care"]
IDEA = "A calm online counselling practice for young professionals dealing with work stress."
DRAFT = {"page": {"tagline": "Calm, practical counselling.", "about": "North Star offers collaborative, skill-building sessions with clear next steps.",
                  "services": [{"title": "Consultation", "description": "A first conversation."}], "faq": [], "what_to_expect": ["A shared plan"]},
         "welcome_email": {"subject": "Welcome", "body": "Thank you for booking with North Star. We look forward to meeting you."},
         "checklist": ["Review page", "Confirm domain", "Add slots"]}


def _llm(*replies):
    """Mock model: each call pops the next reply (dict -> JSON); extra calls reuse the last. Returns (text, in, out) tokens."""
    queue = list(replies)

    def fake(system, prompt, *, max_tokens):
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        return (item if isinstance(item, str) else json.dumps(item)), 10, 20

    return patch("backend.app.agents.launch._launch_llm", side_effect=fake)


def _godaddy(status=200, available=True):
    calls = []

    def request(method, url, **kw):
        calls.append((method, url))
        r = MagicMock(status_code=status)
        r.json.return_value = {"available": available, "price": 12990000, "currency": "USD"} if "available" in url else {}
        return r

    return calls, patch("backend.app.domains.httpx.request", side_effect=request)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GODADDY_API_KEY", "k")
    monkeypatch.setenv("GODADDY_API_SECRET", "s")
    monkeypatch.setenv("SAARTHI_SERVER_IP", "203.0.113.7")
    monkeypatch.delenv("GODADDY_ALLOW_DNS_WRITE", raising=False)
    monkeypatch.setenv("FAKE_LLM", "0")


@pytest.fixture
def world():
    with SessionLocal() as db:
        users = {}
        for tag, role in (("owner", "practice_owner"), ("owner_b", "practice_owner"), ("admin", "admin"), ("client", "client"), ("ther", "therapist")):
            u = User(email=f"{tag}-{uuid4().hex[:8]}@example.com", password_hash=hash_password("x" * 12), role=role, name=tag)
            db.add(u)
            db.flush()
            users[tag] = u
        mine = Practice(name="North Star", slug=uuid4().hex, owner_id=users["owner"].id, city="Pune", page_json="{}")
        db.add(mine)
        db.commit()
        info = {"pid": mine.id, "emails": {k: (u.email, u.role) for k, u in users.items()}, "uids": [u.id for u in users.values()]}
    h = {k: {"Authorization": f"Bearer {create_access_token(e, r)}"} for k, (e, r) in info["emails"].items()}
    yield {"h": h, "pid": info["pid"]}
    with SessionLocal() as db:
        db.execute(delete(PendingAction).where(PendingAction.practice_id == info["pid"]))
        db.execute(delete(AgentRun).where(AgentRun.practice_id == info["pid"]))
        db.execute(delete(AuditLog).where(AuditLog.entity_id == info["pid"], AuditLog.entity_type == "practice"))
        db.execute(delete(User).where(User.id.in_(info["uids"])))
        db.execute(delete(Practice).where(Practice.id == info["pid"]))
        db.commit()


def _run(w, who="owner"):
    r = client.post(f"/owner/practices/{w['pid']}/launch/run", headers=w["h"][who], json={"idea": IDEA})
    assert r.status_code == 202, r.text
    return client.get(f"/owner/practices/{w['pid']}/launch/runs/{r.json()['run_id']}", headers=w["h"][who]).json()


def _approve(w, action):
    return client.post(f"/pending-actions/{action['id']}/approve", headers=w["h"]["owner"] | {"Idempotency-Key": action["idempotency_key"]})


ENDPOINTS = [("post", "/launch/run", {"idea": IDEA}), ("get", "/launch/runs/abc", None), ("get", "/launch", None),
             ("put", "/launch/plans/1", DRAFT), ("post", "/launch/domain/confirm", {"domain": "northstar.com"}),
             ("post", "/launch/domain/apply-dns", None)]


@pytest.mark.parametrize("who", ["owner_b", "ther", "client", "admin"])
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_owner_only_access(world, who, method, path, body):
    r = getattr(client, method)(f"/owner/practices/{world['pid']}{path}", headers=world["h"][who], **({"json": body} if body is not None else {}))
    assert r.status_code == 403


def test_unauthenticated_is_rejected(world):
    assert client.get(f"/owner/practices/{world['pid']}/launch").status_code in (401, 403)


def test_plan_trace_cost_and_approval_only_proposes(world):
    calls, gd = _godaddy()
    with _llm({"names": NAMES}, DRAFT), gd:
        run = _run(world)
    assert run["status"] == "complete"
    tools = [s["tool"] for s in run["steps"]]
    assert tools == ["domain_suggest", "domain_check", "domain_check", "domain_check", "dns_plan", "draft_launch_plan"]
    assert len(tools) <= 8 and run["tokens"] == 60  # 2 model calls x 30 tokens
    action = run["action"]
    assert action["status"] == "pending" and action["tokens_in"] == 20 and action["tokens_out"] == 40 and action["cost_usd"] > 0
    assert [t["tool"] for t in action["trace"]] == tools and all(t["input"] and t["result"] for t in action["trace"])
    plan = action["plan"]
    assert [d["status"] for d in plan["domains"]] == ["available"] * 3 + ["not_checked"] * 2
    assert plan["domains"][0]["price"] == 12.99
    assert {(r["type"], r["name"], r["data"]) for r in plan["dns_plan"]["records"]} == {("A", "@", "203.0.113.7"), ("CNAME", "www", "@")}
    assert {m for m, _ in calls} == {"GET"}  # only availability reads
    with SessionLocal() as db:
        rows = db.query(AgentRun).filter(AgentRun.practice_id == world["pid"], AgentRun.agent == "launch_idea").all()
        assert sum(r.tokens for r in rows) == 60 and any(r.input_short for r in rows)
        assert db.get(Practice, world["pid"]).page_text is None  # nothing applied before approval
    assert _approve(world, action).status_code == 200
    with SessionLocal() as db:
        p = db.get(Practice, world["pid"])
        assert p.page_tagline == DRAFT["page"]["tagline"] and p.status == "draft" and p.custom_domain is None


def test_edit_is_post_checked(world):
    with _llm({"names": NAMES}, DRAFT), _godaddy()[1]:
        action = _run(world)["action"]
    bad = DRAFT | {"checklist": ["We guarantee results", "b", "c"]}
    assert client.put(f"/owner/practices/{world['pid']}/launch/plans/{action['id']}", headers=world["h"]["owner"], json=bad).status_code == 422
    good = DRAFT | {"checklist": ["Edited step", "b", "c"]}
    r = client.put(f"/owner/practices/{world['pid']}/launch/plans/{action['id']}", headers=world["h"]["owner"], json=good)
    assert r.status_code == 200 and r.json()["plan"]["checklist"][0] == "Edited step"


def test_no_dns_or_purchase_without_approval_confirmation_and_flag(world, monkeypatch):
    base = f"/owner/practices/{world['pid']}/launch/domain"
    h = world["h"]["owner"]
    calls, gd = _godaddy()
    with _llm({"names": NAMES}, DRAFT), gd:
        action = _run(world)["action"]
        assert client.post(f"{base}/confirm", headers=h, json={"domain": "northstar.com"}).status_code == 422  # plan not approved
        assert client.post(f"{base}/apply-dns", headers=h | {"Idempotency-Key": "k1"}).status_code == 403  # flag off
        _approve(world, action)
        assert client.post(f"{base}/confirm", headers=h, json={"domain": "unrelated.com"}).status_code == 422
        assert client.post(f"{base}/confirm", headers=h, json={"domain": "northstar.com"}).status_code == 200
        assert client.post(f"{base}/apply-dns", headers=h | {"Idempotency-Key": "k1"}).status_code == 403  # confirmed, flag still off
        assert {m for m, _ in calls} == {"GET"}
        monkeypatch.setenv("GODADDY_ALLOW_DNS_WRITE", "1")
        r1 = client.post(f"{base}/apply-dns", headers=h | {"Idempotency-Key": "k1"})
        r2 = client.post(f"{base}/apply-dns", headers=h | {"Idempotency-Key": "k1"})
    assert r1.status_code == r2.status_code == 200
    writes = [(m, u) for m, u in calls if m != "GET"]
    assert [m for m, _ in writes] == ["PUT", "PUT"]  # once, not replayed
    assert writes[0][1].endswith("/v1/domains/northstar.com/records/A/@") and writes[1][1].endswith("/records/CNAME/www")
    assert not any("purchase" in u for _, u in calls)


def test_apply_dns_needs_confirmed_domain(world, monkeypatch):
    monkeypatch.setenv("GODADDY_ALLOW_DNS_WRITE", "1")
    r = client.post(f"/owner/practices/{world['pid']}/launch/domain/apply-dns", headers=world["h"]["owner"] | {"Idempotency-Key": "x"})
    assert r.status_code == 409


def test_missing_credentials_label_unknown_and_make_no_calls(world, monkeypatch):
    monkeypatch.delenv("GODADDY_API_KEY")
    calls, gd = _godaddy()
    with _llm({"names": NAMES}, DRAFT), gd:
        run = _run(world)
    assert run["status"] == "complete" and calls == []
    doms = run["action"]["plan"]["domains"][:3]
    assert {d["status"] for d in doms} == {"unknown"} and all("credentials" in d["reason"] for d in doms) and all(d["price"] is None for d in doms)


@pytest.mark.parametrize("code", [401, 403])
def test_rejected_credentials_are_unknown_not_faked(world, code):
    _, gd = _godaddy(status=code)
    with _llm({"names": NAMES}, DRAFT), gd:
        doms = _run(world)["action"]["plan"]["domains"][:3]
    assert {d["status"] for d in doms} == {"unknown"} and all("rejected" in d["reason"] for d in doms)


def test_validation_retry_then_success_stays_within_eight_calls(world):
    with _llm({"names": ["bad"]}, {"names": NAMES}, {"page": {}}, DRAFT), _godaddy()[1]:
        run = _run(world)
    tools = [s["tool"] for s in run["steps"]]
    assert run["status"] == "complete" and tools.count("domain_suggest") == 2 and tools.count("draft_launch_plan") == 2 and len(tools) == 8


def test_second_invalid_answer_gives_visible_error_and_no_action(world):
    with _llm({"names": NAMES}, {"page": {}}), _godaddy()[1]:
        run = _run(world)
    assert run["status"] == "failed" and "manually" in run["message"] and run["action"] is None
    with SessionLocal() as db:
        assert db.query(PendingAction).filter(PendingAction.practice_id == world["pid"]).count() == 0


def test_claims_and_diagnoses_are_rejected_by_post_check(world):
    bad = json.loads(json.dumps(DRAFT))
    bad["page"]["about"] = "We guarantee results and treat your depression with supplements for everyone."
    with _llm({"names": NAMES}, bad), _godaddy()[1]:
        run = _run(world)
    assert run["status"] == "failed" and run["action"] is None


def test_budget_exceeded_falls_back_to_manual(world, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with patch("backend.app.agents.launch._budget_exceeded", return_value=True), patch("backend.app.agents.launch.httpx.post") as post:
        run = _run(world)
    assert run["status"] == "unavailable" and run["message"] == "AI unavailable, manual workflow open." and run["action"] is None
    post.assert_not_called()
