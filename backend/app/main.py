from __future__ import annotations

import json
import os
import re
import smtplib
from email.message import EmailMessage
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.agents.launch import run_launch_agent
from backend.app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from backend.app.db import engine, get_db
from backend.app.models import AgentRun, AuditLog, PendingAction, Practice, User, UserRole
from backend.app.safety import check_claims, render_prompt_data, risk_check, validate_ai_output
from backend.app.schemas import (
    MessageResponse,
    PracticeContact,
    PracticeDraft,
    PracticeOut,
    UserCreate,
    UserLogin,
    UserOut,
)

app = FastAPI(title="Counselling Practice Platform")


def _slugify(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (raw or "practice").lower()).strip("-")
    return slug[:120] or "practice"


def _generate_unique_slug(db: Session, raw: str, exclude_id: int | None = None) -> str:
    base = _slugify(raw)
    slug = base
    index = 2
    while True:
        existing = db.query(Practice).filter(Practice.slug == slug)
        if exclude_id is not None:
            existing = existing.filter(Practice.id != exclude_id)
        if existing.first() is None:
            return slug
        slug = f"{base}-{index}"
        index += 1


def _create_publish_action(db: Session, practice: Practice, page: dict[str, object], run_id: str | None = None) -> PendingAction:
    action = PendingAction(
        practice_id=practice.id,
        type="publish_page",
        payload={"practice_id": practice.id, "draft": page, "run_id": run_id},
        status="pending",
        idempotency_key=uuid4().hex,
    )
    db.add(action)
    return action


def _pending_action_result(action: PendingAction) -> dict[str, object]:
    return {
        "id": action.id,
        "type": action.type,
        "status": action.status,
        "practice_id": action.practice_id,
        "idempotency_key": action.idempotency_key,
        "decided_by": action.decided_by,
        "decided_at": action.decided_at.isoformat() if action.decided_at else None,
    }


def _get_owner_pending_action(db: Session, action_id: int, user: User) -> PendingAction:
    action = db.query(PendingAction).filter(PendingAction.id == action_id).with_for_update().first()
    if action is None:
        raise HTTPException(status_code=404, detail="Pending action not found")
    practice = db.query(Practice).filter(Practice.id == action.practice_id).first()
    if user.role != UserRole.practice_owner or practice is None or practice.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return action


def _check_action_key(action: PendingAction, idempotency_key: str | None) -> None:
    if idempotency_key != action.idempotency_key:
        raise HTTPException(status_code=409, detail="A matching Idempotency-Key header is required")


def _build_practice_page(payload: PracticeDraft) -> dict[str, object]:
    specialty_text = ", ".join(payload.specialties) if payload.specialties else "wellbeing"
    tone = payload.tone or "warm and calm"
    if payload.tagline:
        tagline = payload.tagline
    else:
        tagline = f"Compassionate support for {specialty_text} in {payload.location}."
    return {
        "banner": "Demo: use fictional information only.",
        "tagline": tagline,
        "about": (
            f"{payload.name} offers a warm, grounded approach to support people navigating "
            f"{specialty_text} with {tone.lower()} care."
        ),
        "services": [
            {"title": "Initial consultation", "description": f"A first conversation to understand your needs and goals."},
            {"title": "Supportive sessions", "description": f"Gentle, structured support informed by {', '.join(payload.approaches) or 'evidence-based practice'}."},
        ],
        "faq": [
            {"question": "What do sessions look like?", "answer": "Sessions are collaborative, practical, and paced to fit your needs."},
            {"question": "Is this online or in-person?", "answer": f"This practice offers {payload.session_type} sessions."},
        ],
        "what_to_expect": [
            "Clear goals and a collaborative plan",
            "A respectful, trauma-informed approach",
            "Simple next steps between sessions",
        ],
        "location": payload.location,
        "languages": payload.languages,
        "specialties": payload.specialties,
        "approaches": payload.approaches,
        "fee_range": payload.fee_range,
        "session_type": payload.session_type,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "Hello from Caddy"}


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    return {"status": "ok", "db": db_status}


@app.post("/auth/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="User already exists")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        language=payload.language,
        name=payload.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login")
def login(payload: UserLogin, db: Session = Depends(get_db)) -> JSONResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.email, user.role)
    user_payload = UserOut.model_validate(user, from_attributes=True).model_dump()
    response = JSONResponse({"message": "Logged in", "user": user_payload, "token": token})
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@app.post("/practices/draft")
def draft_practice(
    payload: PracticeDraft,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.practice_owner, UserRole.admin)),
) -> dict[str, object]:
    combined_text = " ".join(
        [
            payload.name,
            payload.location,
            " ".join(payload.languages),
            " ".join(payload.specialties),
            " ".join(payload.approaches),
            payload.fee_range,
            payload.tone,
            payload.session_type,
        ]
    )
    if not check_claims(combined_text):
        raise HTTPException(status_code=422, detail="Claims check failed: promotional language is not allowed.")

    page = _build_practice_page(payload)
    practice = Practice(
        name=payload.name,
        slug=_generate_unique_slug(db, payload.name),
        owner_id=current_user.id,
        status="draft",
        verified=False,
        page_json=json.dumps(page),
    )
    db.add(practice)
    db.flush()
    action = _create_publish_action(db, practice, page)
    db.commit()
    db.refresh(practice)
    return {"id": practice.id, "status": practice.status, "slug": practice.slug, "page": page, "pending_action": _pending_action_result(action)}


@app.get("/practices")
def list_practices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if current_user.role == UserRole.admin:
        records = db.query(Practice).all()
    elif current_user.role == UserRole.practice_owner:
        records = db.query(Practice).filter(Practice.owner_id == current_user.id).all()
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    items = []
    for record in records:
        page = json.loads(record.page_json or "{}")
        items.append({
            "id": record.id,
            "name": record.name,
            "slug": record.slug,
            "status": record.status,
            "verified": record.verified,
            "page": page,
        })
    return {"items": items}


@app.get("/practices/public")
def public_practices(
    db: Session = Depends(get_db),
    language: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
    approach: str | None = Query(default=None),
    fee_max: int | None = Query(default=None),
    session_type: str | None = Query(default=None),
) -> dict[str, object]:
    records = db.query(Practice).filter(Practice.status == "published", Practice.verified.is_(True)).all()
    items = []
    for record in records:
        page = json.loads(record.page_json or "{}")
        fee = page.get("fee_range")
        fee_value = None
        if isinstance(fee, str):
            parts = [part for part in re.findall(r"\d+", fee) if part]
            fee_value = int(parts[-1]) if parts else None
        if language and language.lower() not in {entry.lower() for entry in page.get("languages", [])}:
            continue
        if specialty and specialty.lower() not in {entry.lower() for entry in page.get("specialties", [])}:
            continue
        if approach and approach.lower() not in {entry.lower() for entry in page.get("approaches", [])}:
            continue
        if fee_max is not None and fee_value is not None and fee_value > fee_max:
            continue
        if session_type and str(page.get("session_type", "")).lower() != session_type.lower():
            continue
        items.append({
            "id": record.id,
            "name": record.name,
            "slug": record.slug,
            "status": record.status,
            "verified": record.verified,
            "page": page,
        })
    return {"items": items, "total": len(items)}


@app.get("/p/{slug}")
def public_practice_detail(slug: str, db: Session = Depends(get_db)) -> dict[str, object]:
    record = db.query(Practice).filter(Practice.slug == slug, Practice.status == "published", Practice.verified.is_(True)).first()
    if not record:
        raise HTTPException(status_code=404, detail="Practice not found")
    page = json.loads(record.page_json or "{}")
    payload = {"banner": "Demo: use fictional information only.", "practice": {"id": record.id, "name": record.name, "slug": record.slug, "verified": record.verified, "page": page}}
    return payload


@app.post("/admin/practices/{practice_id}/verify")
def verify_practice(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin)),
) -> dict[str, object]:
    record = db.query(Practice).filter(Practice.id == practice_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Practice not found")
    record.verified = True
    db.add(AuditLog(
        action="practice.verify",
        actor_id=current_user.id,
        entity_type="practice",
        entity_id=record.id,
        details={"verified": True},
    ))
    db.commit()
    db.refresh(record)
    return {"id": record.id, "status": record.status, "verified": record.verified}


@app.get("/pending-actions")
def list_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if current_user.role != UserRole.practice_owner:
        raise HTTPException(status_code=403, detail="Access denied")
    rows = (
        db.query(PendingAction)
        .join(Practice, Practice.id == PendingAction.practice_id)
        .filter(Practice.owner_id == current_user.id)
        .order_by(PendingAction.created_at.desc(), PendingAction.id.desc())
        .all()
    )
    return {"items": [_pending_action_result(row) | {"payload": row.payload} for row in rows]}


@app.post("/pending-actions/{action_id}/approve")
def approve_pending_action(
    action_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action = _get_owner_pending_action(db, action_id, current_user)
    if action.status == "pending":
        _check_action_key(action, idempotency_key)
        if action.type != "publish_page":
            raise HTTPException(status_code=422, detail="Unsupported pending action type")
        practice = db.query(Practice).filter(Practice.id == action.practice_id).first()
        draft = action.payload.get("draft")
        if practice is None or not isinstance(draft, dict):
            raise HTTPException(status_code=409, detail="Pending action draft is unavailable")
        practice.page_json = json.dumps(draft)
        practice.status = "published"
        action.status = "approved"
        action.decided_by = current_user.id
        action.decided_at = datetime.utcnow()
        replay = False
    else:
        replay = True

    db.add(AuditLog(
        action="pending_action.approve",
        actor_id=current_user.id,
        entity_type="pending_action",
        entity_id=action.id,
        details={"result_status": action.status, "idempotent_replay": replay},
    ))
    db.commit()
    return _pending_action_result(action)


@app.post("/pending-actions/{action_id}/reject")
def reject_pending_action(
    action_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action = _get_owner_pending_action(db, action_id, current_user)
    if action.status == "pending":
        _check_action_key(action, idempotency_key)
        action.status = "rejected"
        action.decided_by = current_user.id
        action.decided_at = datetime.utcnow()
        replay = False
    else:
        replay = True

    db.add(AuditLog(
        action="pending_action.reject",
        actor_id=current_user.id,
        entity_type="pending_action",
        entity_id=action.id,
        details={"result_status": action.status, "idempotent_replay": replay},
    ))
    db.commit()
    return _pending_action_result(action)


@app.post("/practices/contact")
def contact_practice(payload: PracticeContact) -> dict[str, str]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@localhost")
    if not smtp_host or not smtp_user or not smtp_pass:
        return {"status": "queued", "message": "Contact request captured; demo SMTP is not configured."}

    message = EmailMessage()
    message["Subject"] = f"New contact request for {payload.practice}"
    message["From"] = smtp_from
    message["To"] = smtp_from
    message.set_content(
        f"Name: {payload.name}\nEmail: {payload.email}\nPractice: {payload.practice}\n\n{payload.message}"
    )

    with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "1025"))) as connection:
        connection.login(smtp_user, smtp_pass)
        connection.send_message(message)
    return {"status": "sent", "message": "Contact request sent."}


@app.post("/practices/{practice_id}/draft-with-agent")
def draft_practice_with_agent(
    practice_id: int,
    payload: dict[str, object],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")
    if practice.owner_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    launch_input = {
        "name": str(payload.get("name", practice.name)),
        "location": str(payload.get("location", "Bengaluru")),
        "languages": payload.get("languages", []) or [],
        "specialties": payload.get("specialties", []) or [],
        "approaches": payload.get("approaches", []) or [],
        "fee_range": str(payload.get("fee_range", "2000-3000")),
        "tone": str(payload.get("tone", "warm and calm")),
        "session_type": str(payload.get("session_type", "online")),
    }
    try:
        result = run_launch_agent(launch_input)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    page_json = json.dumps(result["page"])
    practice.page_json = page_json
    practice.status = "draft"
    practice.verified = False
    db.add(practice)
    for run in result.get("agent_runs", []):
        db.add(AgentRun(practice_id=practice.id, run_id=str(run["run_id"]), step=int(run["step"]), tool=str(run["tool"]), summary=str(run["summary"])))
    action = _create_publish_action(db, practice, result["page"], str(result.get("run_id", "")))
    db.commit()
    db.refresh(practice)

    return {"id": practice.id, "status": practice.status, "slug": practice.slug, "page": result["page"], "run_id": result.get("run_id"), "pending_action": _pending_action_result(action)}


@app.get("/practices/{practice_id}/agent-runs")
def practice_agent_runs(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")
    if practice.owner_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied")

    rows = db.query(AgentRun).filter(AgentRun.practice_id == practice_id).order_by(AgentRun.step.asc()).all()
    return {"items": [{"run_id": row.run_id, "step": row.step, "tool": row.tool, "summary": row.summary, "created_at": row.created_at.isoformat()} for row in rows]}


@app.post("/demo/safety-check")
def demo_safety_check(text: str) -> dict[str, object]:
    result = risk_check(text)
    return {
        "flagged": result["flagged"],
        "message": result["message"],
        "blocked": result["blocked"],
    }


@app.post("/demo/prompt-guard")
def demo_prompt_guard(text: str) -> dict[str, str]:
    safe_text = render_prompt_data(text)
    return {"sanitized": safe_text}


@app.post("/demo/ai-output-validator")
def demo_ai_output_validator(text: str) -> MessageResponse:
    valid, reason = validate_ai_output(text)
    if not valid:
        raise HTTPException(status_code=422, detail=reason)
    return MessageResponse(message="Approved")
