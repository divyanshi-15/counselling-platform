"""Idea-to-launch for practice owners. The agent proposes one plan (a pending_action); the owner approves, edits or
rejects it. Confirming a domain and applying DNS are separate owner actions; no domain is ever bought here, and DNS
is written only when GODADDY_ALLOW_DNS_WRITE=1."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import domains
from backend.app.agents import launch
from backend.app.auth import require_roles
from backend.app.db import SessionLocal, get_db
from backend.app.models import AgentRun, AuditLog, PendingAction, Practice, User, UserRole
from backend.app.ratelimit import rate_limit

router = APIRouter(tags=["launch"])
owner_only = require_roles(UserRole.practice_owner)
launch_rate_limit = rate_limit("launch_ai", "RATE_LIMIT_AI_PER_MIN", 10)
AGENT = "launch_idea"
TERMINAL = {"run_complete": "complete", "run_unavailable": "unavailable", "run_failed": "failed"}
PAGE_EDITABLE = ("draft", "changes_requested", "verified")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IdeaIn(_In):
    idea: str = Field(min_length=10, max_length=1000)


class DomainIn(_In):
    domain: str = Field(min_length=4, max_length=253)


class PlanEditIn(launch.ModelLaunchDraft):
    slug: str | None = Field(default=None, min_length=3, max_length=40)


class StepOut(BaseModel):
    step: int
    tool: str
    input: str | None
    result: str
    tokens: int


class PlanActionOut(BaseModel):
    id: int
    status: str
    idempotency_key: str
    plan: dict[str, Any]
    trace: list[dict[str, Any]]
    tokens_in: int
    tokens_out: int
    cost_usd: float | None


class RunOut(BaseModel):
    run_id: str
    status: str  # running | complete | unavailable | failed
    steps: list[StepOut]
    tokens: int
    message: str | None
    action: PlanActionOut | None


class LaunchStateOut(BaseModel):
    custom_domain: str | None
    domain_confirmed_at: str | None
    dns_write_enabled: bool
    dns_plan: dict[str, Any] | None
    latest: PlanActionOut | None


class DnsApplyOut(BaseModel):
    domain: str
    applied: bool
    records: list[dict[str, Any]]


def _practice(db: Session, practice_id: int, user: User) -> Practice:
    practice = db.get(Practice, practice_id)
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    if practice.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return practice


def _plan_actions(db: Session, practice_id: int) -> list[PendingAction]:
    return (db.query(PendingAction).filter(PendingAction.practice_id == practice_id, PendingAction.type == "launch_plan")
            .order_by(PendingAction.id.desc()).all())


def _action_out(row: PendingAction) -> dict[str, Any]:
    p = row.payload
    return {"id": row.id, "status": row.status, "idempotency_key": row.idempotency_key, "plan": p["plan"], "trace": p["trace"],
            "tokens_in": p["tokens_in"], "tokens_out": p["tokens_out"], "cost_usd": p["cost_usd"]}


def _step_out(row: AgentRun) -> dict[str, Any]:
    return {"step": row.step, "tool": row.tool, "input": row.input_short, "result": row.summary, "tokens": row.tokens}


# ---------- run (background, live steps are polled) ----------

def _slug_taken(practice_id: int):
    def taken(slug: str) -> bool:  # our own database only; the practice's current slug counts as free for itself
        with SessionLocal() as db:
            return db.query(Practice.id).filter(Practice.slug == slug, Practice.id != practice_id).first() is not None
    return taken


def _execute(run_id: str, practice_id: int, user_id: int, idea: str, practice_ctx: dict[str, Any]) -> None:
    def write(step: int, tool: str, summary: str, input_short: str | None = None, tokens: int = 0) -> None:
        with SessionLocal() as db:
            db.add(AgentRun(practice_id=practice_id, run_id=run_id, step=step, tool=tool, summary=summary, agent=AGENT,
                            actor_user_id=user_id, input_short=input_short, tokens=tokens))
            db.commit()

    def on_step(e: dict[str, Any]) -> None:
        write(e["step"], e["tool"], e["result"], e["input"], e["tokens"])

    try:
        result = launch.run_idea_launch(idea, practice_ctx, slug_taken=_slug_taken(practice_id), on_step=on_step)
    except Exception:
        write(99, "run_failed", launch.AI_FAILED_MSG)
        return
    if result["status"] == "complete":
        with SessionLocal() as db:
            db.add(PendingAction(practice_id=practice_id, type="launch_plan", status="pending", idempotency_key=uuid4().hex,
                                 payload={"practice_id": practice_id, "run_id": run_id, "plan": result["plan"], "trace": result["trace"],
                                          "tokens_in": result["tokens_in"], "tokens_out": result["tokens_out"], "cost_usd": result["cost_usd"]}))
            db.commit()
    write(99, f"run_{result['status']}" if result["status"] != "complete" else "run_complete", result["message"] or "Plan ready for your review.")


@router.post("/owner/practices/{practice_id}/launch/run", dependencies=[Depends(launch_rate_limit)], response_model=RunOut, status_code=202)
def start_run(practice_id: int, payload: IdeaIn, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    practice = _practice(db, practice_id, user)
    run_id = uuid4().hex
    ctx = {"name": practice.name, "city": practice.city, "specialisations": practice.specialisations, "languages": practice.languages,
           "session_formats": practice.session_formats}
    background.add_task(_execute, run_id, practice.id, user.id, payload.idea, ctx)
    return {"run_id": run_id, "status": "running", "steps": [], "tokens": 0, "message": None, "action": None}


@router.get("/owner/practices/{practice_id}/launch/runs/{run_id}", response_model=RunOut)
def get_run(practice_id: int, run_id: str, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    _practice(db, practice_id, user)
    rows = (db.query(AgentRun).filter(AgentRun.practice_id == practice_id, AgentRun.run_id == run_id, AgentRun.agent == AGENT)
            .order_by(AgentRun.step.asc()).all())
    terminal = next((r for r in rows if r.tool in TERMINAL), None)
    steps = [r for r in rows if r.tool not in TERMINAL]
    action = None
    if terminal is not None and TERMINAL[terminal.tool] == "complete":
        action = next((a for a in _plan_actions(db, practice_id) if a.payload.get("run_id") == run_id), None)
    return {"run_id": run_id, "status": TERMINAL[terminal.tool] if terminal else "running", "steps": [_step_out(r) for r in steps],
            "tokens": sum(r.tokens for r in steps), "message": terminal.summary if terminal else None,
            "action": _action_out(action) if action else None}


# ---------- state, edit ----------

@router.get("/owner/practices/{practice_id}/launch", response_model=LaunchStateOut)
def launch_state(practice_id: int, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    practice = _practice(db, practice_id, user)
    latest = next(iter(_plan_actions(db, practice_id)), None)
    return {"custom_domain": practice.custom_domain,
            "domain_confirmed_at": practice.domain_confirmed_at.isoformat() if practice.domain_confirmed_at else None,
            "dns_write_enabled": domains.dns_write_enabled(),
            "dns_plan": domains.dns_plan(practice.custom_domain) if practice.custom_domain else None,
            "latest": _action_out(latest) if latest else None}


@router.put("/owner/practices/{practice_id}/launch/plans/{action_id}", response_model=PlanActionOut)
def edit_plan(practice_id: int, action_id: int, payload: PlanEditIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    _practice(db, practice_id, user)
    action = db.get(PendingAction, action_id)
    if action is None or action.practice_id != practice_id or action.type != "launch_plan":
        raise HTTPException(status_code=404, detail="Launch plan not found")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail="This plan has already been decided")
    if violations := launch.launch_violations(payload):
        raise HTTPException(status_code=422, detail="This text cannot be saved: " + "; ".join(violations))
    plan = action.payload["plan"] | payload.model_dump(exclude={"slug"})
    if payload.slug is not None:
        if not launch.SLUG_RE.match(payload.slug):
            raise HTTPException(status_code=422, detail="Use lowercase letters, digits and single hyphens only")
        if _slug_taken(practice_id)(payload.slug):
            raise HTTPException(status_code=409, detail="That address is already in use")
        plan["chosen_slug"] = payload.slug
    action.payload = action.payload | {"plan": plan}
    db.add(AuditLog(action="launch.plan_edit", actor_id=user.id, entity_type="pending_action", entity_id=action.id, details={}))
    db.commit()
    return _action_out(action)


def apply_launch_plan(db: Session, action: PendingAction, user: User) -> None:
    """Owner approval saves the page text as the editable page draft. Publishing and domains stay separate steps."""
    practice = db.get(Practice, action.practice_id)
    if practice is None or practice.verification_status not in PAGE_EDITABLE:
        raise HTTPException(status_code=409, detail="The page cannot be changed right now")
    plan = launch.ModelLaunchDraft.model_validate({k: action.payload["plan"][k] for k in ("page", "welcome_email", "checklist")})
    if launch.launch_violations(plan):
        raise HTTPException(status_code=422, detail="This plan contains claims that cannot be published")
    chosen = action.payload["plan"].get("chosen_slug")
    if chosen and chosen != practice.slug:
        if not launch.SLUG_RE.match(chosen) or db.query(Practice.id).filter(Practice.slug == chosen, Practice.id != practice.id).first():
            raise HTTPException(status_code=409, detail="That page address is no longer available; choose another and approve again")
        practice.slug = chosen
    page = plan.page
    parts = [page.about]
    if page.services:
        parts.append("**Services**\n" + "\n".join(f"- {s.get('title', '')}: {s.get('description', '')}" for s in page.services))
    if page.what_to_expect:
        parts.append("**What to expect**\n" + "\n".join(f"- {w}" for w in page.what_to_expect))
    practice.page_tagline, practice.page_text = page.tagline, "\n\n".join(parts)
    practice.page_source, practice.page_updated_at = "ai", datetime.now(timezone.utc)
    action.status = "approved"
    action.decided_by = user.id
    action.decided_at = datetime.now(timezone.utc)


# ---------- domain: confirm, then (optionally) apply DNS ----------

@router.post("/owner/practices/{practice_id}/launch/domain/confirm", response_model=LaunchStateOut)
def confirm_domain(practice_id: int, payload: DomainIn, db: Session = Depends(get_db), user: User = Depends(owner_only)):
    practice = _practice(db, practice_id, user)
    domain = payload.domain.lower()
    approved = [a for a in _plan_actions(db, practice_id) if a.status == "approved"]
    options = {o["domain"]: o for a in approved for o in a.payload["plan"]["domains"]}
    if domain not in options or options[domain]["status"] == "taken":
        raise HTTPException(status_code=422, detail="Choose an available domain from an approved launch plan")
    practice.custom_domain, practice.domain_confirmed_at = domain, datetime.now(timezone.utc)
    db.add(AuditLog(action="launch.domain_confirm", actor_id=user.id, entity_type="practice", entity_id=practice.id, details={"domain": domain}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That domain is already used by another practice") from None
    return launch_state(practice_id, db, user)


@router.post("/owner/practices/{practice_id}/launch/domain/apply-dns", response_model=DnsApplyOut)
def apply_dns(practice_id: int, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
              db: Session = Depends(get_db), user: User = Depends(owner_only)):
    practice = _practice(db, practice_id, user)
    if not domains.dns_write_enabled():
        raise HTTPException(status_code=403, detail="DNS changes are turned off on this server. Add the records at your registrar.")
    if not practice.custom_domain or practice.domain_confirmed_at is None:
        raise HTTPException(status_code=409, detail="Confirm a domain first")
    if not idempotency_key:
        raise HTTPException(status_code=409, detail="An Idempotency-Key header is required")
    plan = domains.dns_plan(practice.custom_domain)
    records = plan["records"]
    if not records:
        raise HTTPException(status_code=409, detail=str(plan["note"]))
    prior = [a for a in db.query(AuditLog).filter(AuditLog.action == "launch.dns_apply", AuditLog.entity_id == practice.id).all()
             if a.details.get("idempotency_key") == idempotency_key and a.details.get("domain") == practice.custom_domain]
    if not prior:
        try:
            domains.get_provider().apply_records(practice.custom_domain, [domains.DnsRecord(**r) for r in records])
        except domains.DnsWriteError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        db.add(AuditLog(action="launch.dns_apply", actor_id=user.id, entity_type="practice", entity_id=practice.id,
                        details={"domain": practice.custom_domain, "idempotency_key": idempotency_key}))
        db.commit()
    return {"domain": practice.custom_domain, "applied": True, "records": records}
