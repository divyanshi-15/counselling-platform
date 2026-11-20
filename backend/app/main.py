from __future__ import annotations

import json
import os
import re
import smtplib
from contextlib import asynccontextmanager
from email.message import EmailMessage
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.agents.copilot import CopilotError, prepare_my_day
from backend.app.agents.launch import run_launch_agent
from backend.app.agents.monitor import run_overnight_check
from backend.app.scheduler import start_scheduler
from backend.app.auth import (
    therapist_has_client,
    create_access_token,
    get_current_user,
    get_optional_current_user,
    hash_password,
    require_roles,
    require_therapist_of_client,
    verify_password,
)
from backend.app import fake_llm
from backend.app.db import engine, get_db
from backend.app.clinical import assessment_total, phq9_item9_positive, raise_risk_alert, scan_client_text
from backend.app.models import (
    AgentRun,
    Alert,
    Assessment,
    Assignment,
    Exercise,
    CasePlan,
    CopilotBriefing,
    TherapySession,
    AuditLog,
    AvailabilitySlot,
    Booking,
    IntakeForm,
    IntakeResponse,
    PendingAction,
    Practice,
    TherapistProfile,
    User,
    UserRole,
)
from backend.app.analytics import router as analytics_router
from backend.app.admin_queue import router as admin_queue_router
from backend.app.contact import router as contact_router
from backend.app.launch_flow import apply_launch_plan, router as launch_router
from backend.app.verification import profile_dict, router as verification_router
from backend.app.practice_setup import generate_unique_slug as _generate_unique_slug, router as practice_setup_router
from backend.app.braindump import DraftEdit, router as braindump_router
from backend.app.journeys import approve_journey_draft, router as journeys_router
from backend.app.skills import router as skills_router
from backend.app.exercises import approved_exercises, template_for, router as exercises_router, with_notice
from backend.app.ratelimit import client_rate_limit, contact_rate_limit
from backend.app.rag import index_session_notes
from backend.app.safety import CRISIS_MESSAGE, check_claims, clinical_output_violations, render_prompt_data, risk_scan, validate_ai_output
from backend.app.schemas import (
    PublicPracticeDetailOut, PublicPracticesOut, PublicTherapist, PublicTherapistsOut,
    AdminTherapistsOut, AgentRunsOut, AlertItem, AlertsOut, OwnerActionsOut, PracticeDraftOut, PracticesOut, AssessmentOut, AssessmentsOut, BriefingsOut, CasePlanOut, CasePlansOut,
    OvernightOut, PendingActionOut, PrepareDayOut, SessionNotesOut, TherapistActionsOut,
    TherapistBookingsOut, TherapistProfileOut,
    MessageResponse,
    AssessmentIn,
    AvailabilityOut,
    MySlotOut,
    MySlotsOut,
    AvailabilitySlotIn,
    BookingOut,
    CasePlanIn,
    ClientDashboardOut,
    IntakeFormOut,
    IntakeResponseOut,
    IntakeSubmitOut,
    RoomOut,
    SessionNotesIn,
    BookingIn,
    IntakeFormIn,
    IntakeResponseIn,
    PracticeContact,
    PracticeDraft,
    PracticeOut,
    TherapistProfileIn,
    UserCreate,
    UserLogin,
    UserOut,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    fake_llm.assert_safe_config()
    scheduler = start_scheduler()
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Counselling Practice Platform", lifespan=lifespan, root_path="/api")
app.include_router(exercises_router)
app.include_router(braindump_router)
app.include_router(skills_router)
app.include_router(journeys_router)
app.include_router(analytics_router)
app.include_router(verification_router)
app.include_router(admin_queue_router)
app.include_router(practice_setup_router)
app.include_router(launch_router)
app.include_router(contact_router)


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


def _notes_label(db: Session, user_id: int | None, at: datetime | None) -> str | None:
    if at is None:
        return None
    who = db.get(User, user_id) if user_id else None
    return f"AI-drafted, approved by {who.name if who else 'therapist'} on {at.date().isoformat()}"


def _next_plan(latest: CasePlan, action: PendingAction, now: datetime) -> dict[str, object]:
    """Fields of the case_plan version an apply_plan_update approval creates. The formulation is never touched:
    the approved AI draft goes to update_notes. Used by both preview and apply."""
    return {"approach": latest.approach, "goals_json": latest.goals_json, "formulation_text": latest.formulation_text,
            "update_notes": str(action.payload.get("update_text", "")),
            "update_notes_approved_by": action.assignee_user_id, "update_notes_approved_at": now}


def _plan_diff(db: Session, action: PendingAction) -> dict[str, object] | None:
    client_id = action.payload.get("client_id")
    if not isinstance(client_id, int) or action.assignee_user_id is None:
        return None
    latest = (db.query(CasePlan).filter(CasePlan.client_id == client_id, CasePlan.therapist_user_id == action.assignee_user_id)
              .order_by(CasePlan.version.desc()).first())
    if latest is None:
        return None
    nxt = _next_plan(latest, action, datetime.now(timezone.utc))
    snap = lambda approach, goals, text, notes, label: {  # noqa: E731
        "approach": approach, "goals": [str(g.get("text", "")) for g in goals], "formulation": text,
        "update_notes": notes, "update_notes_label": label}
    before = snap(latest.approach, latest.goals_json, latest.formulation_text, latest.update_notes,
                  _notes_label(db, latest.update_notes_approved_by, latest.update_notes_approved_at))
    after = snap(nxt["approach"], nxt["goals_json"], nxt["formulation_text"], nxt["update_notes"],
                 _notes_label(db, nxt["update_notes_approved_by"], nxt["update_notes_approved_at"]))
    return {"before": before, "after": after,
            "changed": [k for k in ("approach", "goals", "formulation", "update_notes") if before[k] != after[k]],
            "stale": latest.id != action.payload.get("base_plan_id")}


def _action_preview(db: Session, action: PendingAction) -> dict[str, object]:
    """Server-computed: who the action concerns and exactly what would reach the client on approval."""
    client_id = action.payload.get("client_id")
    client = db.query(User).filter(User.id == client_id).first() if isinstance(client_id, int) else None
    if action.type in ("release_exercise", "brain_dump"):
        draft = action.payload.get("draft")
        slug = draft.get("exercise") if action.type == "brain_dump" and isinstance(draft, dict) else action.payload.get("exercise")
        ex = db.query(Exercise).filter(Exercise.slug == slug).first()
        if ex is not None:
            title, template = template_for(ex)
            labels = [str(f.get("label", f.get("id", ""))) for f in (template.get("fields") or []) if isinstance(f, dict)]
            view = {"kind": "exercise", "title": title, "fields": labels,
                    "note": "Appears under \"Approved exercises\" on the client's dashboard. Nothing else is sent."}
            return {"client_name": client.name if client else None, "client_view": view}
    if action.type == "journey_draft":
        draft = action.payload.get("draft") if isinstance(action.payload.get("draft"), dict) else {}
        steps = draft.get("steps") or []
        return {"client_name": client.name if client else None,
                "client_view": {"kind": "journey", "title": draft.get("title_en"),
                                "fields": [f"Week {s.get('week')}: {s.get('text_en')}" for s in steps if isinstance(s, dict)],
                                "note": "Appears on the client's dashboard as a programme starting today. Nothing else is sent."}}
    if action.type == "brain_dump":
        return {"client_name": client.name if client else None,
                "client_view": {"kind": "nothing", "note": "Nothing reaches the client. Approving marks this note as reviewed."}}
    note = ("Nothing reaches the client. This adds a new version to your own case plan only."
            if action.type == "apply_plan_update" else "Nothing reaches the client. This is a private briefing for you.")
    out: dict[str, object] = {"client_name": client.name if client else None, "client_view": {"kind": "nothing", "note": note}}
    if action.type == "apply_plan_update":
        out["diff"] = _plan_diff(db, action)
    return out


def _pending_action_result(action: PendingAction) -> dict[str, object]:
    return {
        "id": action.id,
        "type": action.type,
        "status": action.status,
        "practice_id": action.practice_id,
        "idempotency_key": action.idempotency_key,
        "decided_by": action.decided_by,
        "decided_at": (action.decided_at.replace(tzinfo=timezone.utc).isoformat() if action.decided_at else None),  # naive column stores UTC
    }


OWNER_ACTION_TYPES = {"publish_page", "launch_plan"}
THERAPIST_ACTION_TYPES = {"copilot_briefing", "release_exercise", "apply_plan_update", "brain_dump", "journey_draft"}


def _get_owner_pending_action(db: Session, action_id: int, user: User) -> PendingAction:
    action = db.query(PendingAction).filter(PendingAction.id == action_id).with_for_update().first()
    if action is None:
        raise HTTPException(status_code=404, detail="Pending action not found")
    if action.type in THERAPIST_ACTION_TYPES:
        if user.role != UserRole.therapist or action.assignee_user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        return action
    practice = db.query(Practice).filter(Practice.id == action.practice_id).first()
    if action.type not in OWNER_ACTION_TYPES or user.role != UserRole.practice_owner or practice is None or practice.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return action


def _decide_briefing(db: Session, action: PendingAction, user: User, decision: str) -> None:
    """Therapist decision on a copilot briefing. Marks the draft only; nothing is sent to the client."""
    briefing = db.query(CopilotBriefing).filter(CopilotBriefing.id == action.payload.get("briefing_id"),
                                                CopilotBriefing.therapist_user_id == user.id).first()
    if briefing is None:
        raise HTTPException(status_code=409, detail="Briefing draft is unavailable")
    briefing.status = decision
    action.status = decision
    action.decided_by = user.id
    action.decided_at = datetime.now(timezone.utc)


def _release_exercise(db: Session, action: PendingAction, user: User, slug: object = None) -> None:
    """Therapist approval creates the assignment. action.status gates replays, pending_action_id is unique."""
    client_id = action.payload.get("client_id")
    exercise = db.query(Exercise).filter(Exercise.slug == (slug or action.payload.get("exercise"))).first()
    if exercise is None or not isinstance(client_id, int) or not therapist_has_client(db, user.id, client_id):
        raise HTTPException(status_code=409, detail="Exercise release is unavailable")
    db.add(Assignment(client_id=client_id, therapist_user_id=user.id, exercise_id=exercise.id,
                      pending_action_id=action.id, status="assigned"))
    action.status = "approved"
    action.decided_by = user.id
    action.decided_at = datetime.now(timezone.utc)


def _approve_brain_dump(db: Session, action: PendingAction, user: User) -> None:
    """Approval releases the draft's exercise through the normal release path; a note with no exercise is just reviewed."""
    draft = action.payload.get("draft")
    slug = draft.get("exercise") if isinstance(draft, dict) else None
    if slug:
        _release_exercise(db, action, user, slug)
        return
    if not therapist_has_client(db, user.id, action.payload.get("client_id", -1)):
        raise HTTPException(status_code=409, detail="This note is unavailable")
    action.status = "approved"
    action.decided_by = user.id
    action.decided_at = datetime.now(timezone.utc)


def _apply_plan_update(db: Session, action: PendingAction, user: User) -> None:
    """Therapist approval creates a new case_plan version. Refuses if the plan changed since the draft."""
    client_id = action.payload.get("client_id")
    if not isinstance(client_id, int) or not therapist_has_client(db, user.id, client_id):
        raise HTTPException(status_code=409, detail="Plan update is unavailable")
    latest = (db.query(CasePlan).filter(CasePlan.client_id == client_id, CasePlan.therapist_user_id == user.id)
              .order_by(CasePlan.version.desc()).with_for_update().first())
    if latest is None or latest.id != action.payload.get("base_plan_id"):
        raise HTTPException(status_code=409, detail="The plan changed since this draft; reject it and re-run the check")
    now = datetime.now(timezone.utc)
    db.add(CasePlan(client_id=client_id, therapist_user_id=user.id, version=latest.version + 1, approved_at=now,
                    **_next_plan(latest, action, now)))
    action.status = "approved"
    action.decided_by = user.id
    action.decided_at = now


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


def _public_therapist_query(db: Session, therapist_id: int | None = None):
    query = (
        db.query(TherapistProfile, User, Practice)
        .join(User, User.id == TherapistProfile.user_id)
        .join(Practice, Practice.id == TherapistProfile.practice_id)
        .filter(
            TherapistProfile.verified.is_(True),
            TherapistProfile.left_practice_at.is_(None),
            Practice.status == "published",
            Practice.verified.is_(True),
        )
    )
    if therapist_id is not None:
        query = query.filter(TherapistProfile.id == therapist_id)
    return query


def _therapist_payload(profile: TherapistProfile, user: User, practice: Practice) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": user.name,
        "bio": profile.bio,
        "approaches": profile.approaches,
        "languages": profile.languages,
        "fee": profile.fee,
        "credentials": profile.credentials,
        "years_experience": profile.years_experience,
        "rating": profile.rating,
        "review_count": profile.review_count,
        "specialisations": profile.specialisations,
        "practice": {"id": practice.id, "name": practice.name, "slug": practice.slug},
    }


def _booking_for_participant(db: Session, booking_id: int, user: User) -> tuple[Booking, AvailabilitySlot, TherapistProfile]:
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    slot = db.query(AvailabilitySlot).filter(AvailabilitySlot.id == booking.availability_slot_id).first()
    profile = db.query(TherapistProfile).filter(TherapistProfile.id == slot.therapist_id).first() if slot else None
    allowed = (
        user.role == UserRole.admin
        or (user.role == UserRole.client and booking.client_id == user.id)
        or (user.role == UserRole.therapist and profile is not None and profile.user_id == user.id)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    if slot is None or profile is None:
        raise HTTPException(status_code=404, detail="Booking details not found")
    return booking, slot, profile


def _send_booking_confirmation(client: User, therapist: User, practice: Practice, slot: AvailabilitySlot) -> str:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not smtp_host or not smtp_user or not smtp_pass:
        return "not_configured"

    starts_at = slot.starts_at.isoformat()
    recipients = [(client.email, "Your counselling session is confirmed"), (therapist.email, "A client booked a session")]
    try:
        with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "1025"))) as connection:
            connection.login(smtp_user, smtp_pass)
            for recipient, subject in recipients:
                message = EmailMessage()
                message["Subject"] = subject
                message["From"] = os.getenv("SMTP_FROM", smtp_user)
                message["To"] = recipient
                message.set_content(
                    f"Practice: {practice.name}\nTherapist: {therapist.name or therapist.email}\n"
                    f"Session time: {starts_at}\n"
                )
                connection.send_message(message)
    except (OSError, smtplib.SMTPException):
        return "failed"
    return "sent"


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


SELF_REGISTER_ROLES = {UserRole.client, UserRole.therapist, UserRole.practice_owner}


@app.post("/auth/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if payload.role not in SELF_REGISTER_ROLES:
        raise HTTPException(status_code=403, detail="Role cannot be self-registered")
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=400, detail="User already exists")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        language=payload.language,
        name=payload.name,
        is_verified=False,
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


DEMO_ACCOUNTS = {
    "client": "client@example.com",
    "therapist": "therapist@example.com",
    "practice_owner": "owner@example.com",
}


def _demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "0") == "1"


@app.get("/config")
def public_config() -> dict[str, object]:
    return {"demo_mode": _demo_mode()}


@app.post("/auth/demo-login")
def demo_login(role: str, db: Session = Depends(get_db)) -> JSONResponse:
    email = DEMO_ACCOUNTS.get(role)
    if not _demo_mode() or email is None or role == UserRole.admin:
        raise HTTPException(status_code=404, detail="Not found")
    user = db.query(User).filter(User.email == email).first()
    if not user or user.role == UserRole.admin:
        raise HTTPException(status_code=404, detail="Demo data not seeded")
    token = create_access_token(user.email, user.role)
    response = JSONResponse({"message": "Logged in", "user": UserOut.model_validate(user, from_attributes=True).model_dump()})
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.post("/auth/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("access_token")
    return response


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@app.post("/practices/draft", response_model=PracticeDraftOut)
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


@app.get("/practices", response_model=PracticesOut)
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


@app.get("/practices/public", response_model=PublicPracticesOut)
def public_practices(
    db: Session = Depends(get_db),
    language: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
    approach: str | None = Query(default=None),
    fee_max: int | None = Query(default=None),
    session_type: str | None = Query(default=None),
    city: str | None = Query(default=None),
    specialisation: str | None = Query(default=None),
) -> dict[str, object]:
    specialty = specialty or specialisation
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
        if city and city.strip().lower() not in str(page.get("location", "")).lower():
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


@app.get("/p/{slug}", response_model=PublicPracticeDetailOut)
def public_practice_detail(slug: str, db: Session = Depends(get_db)) -> dict[str, object]:
    record = db.query(Practice).filter(Practice.slug == slug, Practice.status == "published", Practice.verified.is_(True)).first()
    if not record:
        raise HTTPException(status_code=404, detail="Practice not found")
    page = json.loads(record.page_json or "{}")
    payload = {"practice": {"id": record.id, "name": record.name, "slug": record.slug, "verified": record.verified, "page": page}}
    return payload


@app.post("/therapists/me/profile")
def save_therapist_profile(
    payload: TherapistProfileIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    # Practice membership is never set here: it comes only from accepting an invitation (or the seed).
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=403, detail="Join a practice by accepting an invitation first.")
    if profile.left_practice_at is not None:
        raise HTTPException(status_code=409, detail="You were removed from your practice. Ask a practice to invite you.")
    profile.bio = payload.bio
    profile.approaches = payload.approaches
    profile.languages = payload.languages
    profile.fee = payload.fee
    db.commit()
    db.refresh(profile)
    return profile_dict(profile)


@app.get("/therapists/me/profile", response_model=TherapistProfileOut)
def get_therapist_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    return profile_dict(profile)


@app.get("/therapists/public", response_model=PublicTherapistsOut)
def public_therapists(
    practice_id: int | None = Query(default=None),
    city: str | None = Query(default=None),
    language: str | None = Query(default=None),
    specialisation: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = _public_therapist_query(db)
    if practice_id is not None:
        query = query.filter(TherapistProfile.practice_id == practice_id)
    rows = query.order_by(TherapistProfile.id.asc()).all()
    items = []
    for profile, user, practice in rows:
        if language and language.lower() not in {x.lower() for x in profile.languages or []}:
            continue
        if specialisation and specialisation.lower() not in {x.lower() for x in profile.specialisations or []}:
            continue
        if city and city.strip().lower() not in str(json.loads(practice.page_json or "{}").get("location", "")).lower():
            continue
        items.append(_therapist_payload(profile, user, practice))
    return {"items": items}


@app.get("/therapists/public/{therapist_id}", response_model=PublicTherapist)
def public_therapist(therapist_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    row = _public_therapist_query(db, therapist_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Therapist not found")
    return _therapist_payload(*row)


@app.get("/therapists/me/availability", response_model=MySlotsOut)
def my_availability(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    booked = {b for (b,) in db.query(Booking.availability_slot_id).all()}
    rows = (db.query(AvailabilitySlot).filter(AvailabilitySlot.therapist_id == profile.id,
                                              AvailabilitySlot.starts_at > datetime.now(timezone.utc))
            .order_by(AvailabilitySlot.starts_at.asc()).all())
    return {"items": [{"id": r.id, "starts_at": r.starts_at.isoformat(), "ends_at": r.ends_at.isoformat(),
                       "booked": r.id in booked} for r in rows]}


@app.get("/therapists/{therapist_id}/availability", response_model=AvailabilityOut)
def public_therapist_availability(
    therapist_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict[str, object]:
    if current_user is not None and current_user.role == UserRole.practice_owner:
        raise HTTPException(status_code=403, detail="Access denied")
    if _public_therapist_query(db, therapist_id).first() is None:
        raise HTTPException(status_code=404, detail="Therapist not found")
    booked_slot_ids = db.query(Booking.availability_slot_id)
    slots = (
        db.query(AvailabilitySlot)
        .filter(
            AvailabilitySlot.therapist_id == therapist_id,
            AvailabilitySlot.starts_at > datetime.now(timezone.utc),
            ~AvailabilitySlot.id.in_(booked_slot_ids),
        )
        .order_by(AvailabilitySlot.starts_at.asc())
        .all()
    )
    return {"items": [{"id": slot.id, "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat()} for slot in slots]}


@app.delete("/therapists/me/availability/{slot_id}", status_code=204, response_class=Response)
def delete_availability_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> Response:
    slot = db.query(AvailabilitySlot).filter(AvailabilitySlot.id == slot_id).with_for_update().first()
    if slot is None:
        raise HTTPException(status_code=404, detail="Availability slot not found")
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None or slot.therapist_id != profile.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if db.query(Booking).filter(Booking.availability_slot_id == slot.id).first() is not None:
        raise HTTPException(status_code=409, detail="This slot is booked and cannot be removed")
    db.delete(slot)
    db.commit()
    return Response(status_code=204)


@app.post("/therapists/me/availability", response_model=MySlotOut)
def create_availability_slot(
    payload: AvailabilitySlotIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    if payload.starts_at.tzinfo is None or payload.ends_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Availability times must include a timezone")
    if payload.starts_at <= datetime.now(timezone.utc) or payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Availability must be a future, positive-duration slot")
    slot = AvailabilitySlot(therapist_id=profile.id, starts_at=payload.starts_at, ends_at=payload.ends_at)
    db.add(slot)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Availability slot already exists") from exc
    db.refresh(slot)
    return {"id": slot.id, "therapist_id": profile.id, "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat(), "booked": False}


@app.get("/therapists/me/bookings", response_model=TherapistBookingsOut)
def therapist_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    rows = (
        db.query(Booking, AvailabilitySlot, User)
        .join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
        .join(User, User.id == Booking.client_id)
        .filter(AvailabilitySlot.therapist_id == profile.id)
        .order_by(AvailabilitySlot.starts_at.asc())
        .all()
    )
    return {"items": [{"id": booking.id, "status": booking.status,
                       "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat(),
                       "client": {"id": client.id, "name": client.name}}
                      for booking, slot, client in rows]}


@app.post("/bookings", dependencies=[Depends(client_rate_limit)], response_model=BookingOut)
def create_booking(
    payload: BookingIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.client)),
) -> dict[str, object]:
    slot = db.query(AvailabilitySlot).filter(AvailabilitySlot.id == payload.availability_slot_id).first()
    if slot is None:
        raise HTTPException(status_code=404, detail="Availability slot not found")
    public_row = _public_therapist_query(db, slot.therapist_id).first()
    if public_row is None:
        raise HTTPException(status_code=404, detail="Therapist not found")
    if slot.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Availability slot is no longer bookable")
    if db.query(Booking).filter(Booking.availability_slot_id == slot.id).first() is not None:
        raise HTTPException(status_code=409, detail="Availability slot is already booked")

    booking = Booking(client_id=current_user.id, availability_slot_id=slot.id, status="confirmed")
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Availability slot is already booked") from exc
    profile, therapist, practice = public_row
    email_status = _send_booking_confirmation(current_user, therapist, practice, slot)
    return {"id": booking.id, "status": booking.status, "therapist_id": profile.id,
            "starts_at": slot.starts_at.isoformat(), "ends_at": slot.ends_at.isoformat(),
            "confirmation_email": email_status}


@app.get("/bookings/{booking_id}/room", response_model=RoomOut)
def get_booking_room(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.client, UserRole.therapist)),
) -> dict[str, str]:
    booking, _, _ = _booking_for_participant(db, booking_id, current_user)
    return {"room_name": f"cp-{booking.room_token}"}


@app.put("/therapists/me/intake-form")
def save_intake_form(
    payload: IntakeFormIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    field_ids: set[str] = set()
    for field in payload.fields:
        field_id = field.get("id")
        label = field.get("label")
        if not isinstance(field_id, str) or not field_id or not isinstance(label, str) or not label.strip():
            raise HTTPException(status_code=422, detail="Each intake field needs a non-empty id and label")
        if field_id in field_ids:
            raise HTTPException(status_code=422, detail="Intake field ids must be unique")
        field_ids.add(field_id)

    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    form = db.query(IntakeForm).filter(IntakeForm.therapist_id == profile.id).first()
    if form is None:
        form = IntakeForm(therapist_id=profile.id, fields_json=payload.fields)
        db.add(form)
    else:
        form.fields_json = payload.fields
        form.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(form)
    return {"id": form.id, "therapist_id": profile.id, "fields": form.fields_json}


@app.get("/bookings/{booking_id}/intake-form", response_model=IntakeFormOut)
def get_booking_intake_form(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    booking, _, profile = _booking_for_participant(db, booking_id, current_user)
    form = db.query(IntakeForm).filter(IntakeForm.therapist_id == profile.id).first()
    if form is None:
        raise HTTPException(status_code=404, detail="Intake form not found")
    return {"booking_id": booking.id, "fields": form.fields_json}


@app.post("/bookings/{booking_id}/intake-response", dependencies=[Depends(client_rate_limit)],
          response_model=IntakeSubmitOut)
def submit_booking_intake_response(
    booking_id: int,
    payload: IntakeResponseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.client)),
) -> dict[str, object]:
    booking, _, profile = _booking_for_participant(db, booking_id, current_user)
    form = db.query(IntakeForm).filter(IntakeForm.therapist_id == profile.id).first()
    if form is None:
        raise HTTPException(status_code=404, detail="Intake form not found")
    fields = {field["id"]: field for field in form.fields_json}
    unknown_answers = set(payload.answers) - set(fields)
    missing_answers = {field_id for field_id, field in fields.items() if field.get("required", False)} - set(payload.answers)
    if unknown_answers or missing_answers:
        raise HTTPException(status_code=422, detail="Answers must match the intake form fields")
    if db.query(IntakeResponse).filter(IntakeResponse.booking_id == booking.id).first() is not None:
        raise HTTPException(status_code=409, detail="Intake response already submitted")
    response = IntakeResponse(booking_id=booking.id, client_id=current_user.id, answers_json=payload.answers)
    db.add(response)
    risk = scan_client_text(payload.answers)
    if risk:
        db.flush()
        raise_risk_alert(db, therapist_user_id=profile.user_id, client_id=current_user.id,
                         source="intake_response", source_id=response.id, match=risk["match"], text=risk["text"])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Intake response already submitted") from exc
    db.refresh(response)
    return with_notice({"id": response.id, "booking_id": response.booking_id, "answers": response.answers_json,
                        "submitted_at": response.submitted_at.isoformat(),
                        "safety": {"flagged": bool(risk), "message": CRISIS_MESSAGE if risk else None}})


@app.get("/bookings/{booking_id}/intake-response", response_model=IntakeResponseOut)
def get_booking_intake_response(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    booking, _, _ = _booking_for_participant(db, booking_id, current_user)
    response = db.query(IntakeResponse).filter(IntakeResponse.booking_id == booking.id).first()
    if response is None:
        raise HTTPException(status_code=404, detail="Intake response not found")
    return {"id": response.id, "booking_id": response.booking_id, "client_id": response.client_id,
            "answers": response.answers_json, "submitted_at": response.submitted_at.isoformat()}


@app.get("/client/dashboard", dependencies=[Depends(client_rate_limit)], response_model=ClientDashboardOut)
def client_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.client)),
) -> dict[str, object]:
    rows = (
        db.query(Booking, AvailabilitySlot, TherapistProfile, User, Practice)
        .join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
        .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
        .join(User, User.id == TherapistProfile.user_id)
        .join(Practice, Practice.id == TherapistProfile.practice_id)
        .filter(Booking.client_id == current_user.id)
        .order_by(AvailabilitySlot.starts_at.asc())
        .all()
    )
    now = datetime.now(timezone.utc)
    upcoming = next((row for row in rows if row[0].status == "confirmed" and row[1].starts_at >= now), None)
    selected = upcoming or (rows[-1] if rows else None)
    if selected is None:
        return with_notice({"practice": None, "therapist": None, "upcoming_session": None,
                            "approved_exercises": approved_exercises(db, current_user.id)})
    booking, slot, profile, therapist_user, practice = selected
    return with_notice({
        "practice": {"id": practice.id, "name": practice.name, "slug": practice.slug},
        "therapist": _therapist_payload(profile, therapist_user, practice),
        "upcoming_session": ({"id": booking.id, "starts_at": slot.starts_at.isoformat(),
                              "ends_at": slot.ends_at.isoformat(), "status": booking.status} if upcoming else None),
        "approved_exercises": approved_exercises(db, current_user.id),
    })


@app.get("/admin/therapists", response_model=AdminTherapistsOut)
def admin_therapists(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin)),
) -> dict[str, object]:
    rows = (db.query(TherapistProfile, User, Practice).join(User, User.id == TherapistProfile.user_id)
            .join(Practice, Practice.id == TherapistProfile.practice_id).order_by(TherapistProfile.id).all())
    return {"items": [{"id": p.id, "name": u.name, "practice_id": pr.id, "practice_name": pr.name, "verified": p.verified,
                       "verification_status": p.verification_status}
                      for p, u, pr in rows]}


@app.get("/pending-actions", response_model=OwnerActionsOut)
def list_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    if current_user.role != UserRole.practice_owner:
        raise HTTPException(status_code=403, detail="Access denied")
    rows = (
        db.query(PendingAction)
        .join(Practice, Practice.id == PendingAction.practice_id)
        .filter(Practice.owner_id == current_user.id, PendingAction.type.in_(OWNER_ACTION_TYPES))
        .order_by(PendingAction.created_at.desc(), PendingAction.id.desc())
        .all()
    )
    return {"items": [_pending_action_result(row) | {"payload": row.payload} for row in rows]}


@app.post("/pending-actions/{action_id}/approve", response_model=PendingActionOut)
def approve_pending_action(
    action_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action = _get_owner_pending_action(db, action_id, current_user)
    if action.status == "pending" and action.type == "copilot_briefing":
        _check_action_key(action, idempotency_key)
        _decide_briefing(db, action, current_user, "approved")
        replay = False
    elif action.status == "pending" and action.type == "release_exercise":
        _check_action_key(action, idempotency_key)
        _release_exercise(db, action, current_user)
        replay = False
    elif action.status == "pending" and action.type == "apply_plan_update":
        _check_action_key(action, idempotency_key)
        _apply_plan_update(db, action, current_user)
        replay = False
    elif action.status == "pending" and action.type == "brain_dump":
        _check_action_key(action, idempotency_key)
        _approve_brain_dump(db, action, current_user)
        replay = False
    elif action.status == "pending" and action.type == "journey_draft":
        _check_action_key(action, idempotency_key)
        approve_journey_draft(db, action, current_user)
        replay = False
    elif action.status == "pending" and action.type == "launch_plan":
        _check_action_key(action, idempotency_key)
        apply_launch_plan(db, action, current_user)
        replay = False
    elif action.status == "pending":
        _check_action_key(action, idempotency_key)
        if action.type != "publish_page":
            raise HTTPException(status_code=422, detail="Unsupported pending action type")
        practice = db.query(Practice).filter(Practice.id == action.practice_id).first()
        draft = action.payload.get("draft")
        if practice is None or not isinstance(draft, dict):
            raise HTTPException(status_code=409, detail="Pending action draft is unavailable")
        practice.page_json = json.dumps(draft)
        if practice.verification_status == "verified":  # an unverified practice stays a draft until an admin verifies it
            practice.status = "published"
        action.status = "approved"
        action.decided_by = current_user.id
        action.decided_at = datetime.now(timezone.utc)
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


@app.put("/pending-actions/{action_id}/draft", response_model=PendingActionOut)
def edit_brain_dump_draft(
    action_id: int,
    payload: DraftEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Therapist edits a pending brain-dump draft before deciding. Nothing is released until approval."""
    action = _get_owner_pending_action(db, action_id, current_user)
    if action.type != "brain_dump" or action.status != "pending":
        raise HTTPException(status_code=409, detail="This draft cannot be edited")
    if payload.exercise and db.query(Exercise).filter(Exercise.slug == payload.exercise).first() is None:
        raise HTTPException(status_code=422, detail="Unknown exercise")
    violations = clinical_output_violations(" ".join([*payload.themes, *payload.mood_tags, payload.summary]))
    if violations:
        raise HTTPException(status_code=422, detail="Drafts cannot contain diagnoses or medication advice")
    action.payload = action.payload | {"draft": payload.model_dump()}
    db.add(AuditLog(action="pending_action.edit", actor_id=current_user.id, entity_type="pending_action",
                    entity_id=action.id, details={}))
    db.commit()
    return _pending_action_result(action)


@app.post("/pending-actions/{action_id}/reject", response_model=PendingActionOut)
def reject_pending_action(
    action_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action = _get_owner_pending_action(db, action_id, current_user)
    if action.status == "pending":
        _check_action_key(action, idempotency_key)
        if action.type == "copilot_briefing":
            _decide_briefing(db, action, current_user, "rejected")
        action.status = "rejected"
        action.decided_by = current_user.id
        action.decided_at = datetime.now(timezone.utc)
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


@app.post("/practices/contact", dependencies=[Depends(contact_rate_limit)])
def contact_practice(payload: PracticeContact) -> dict[str, str]:
    if scan_client_text({"name": payload.name, "message": payload.message}):
        # Fixed crisis text; the message is not forwarded. No client/therapist is known here, so no alert row.
        return {"status": "crisis", "message": CRISIS_MESSAGE}
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


@app.post("/practices/{practice_id}/draft-with-agent", response_model=PracticeDraftOut)
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
    db.add(practice)
    for run in result.get("agent_runs", []):
        db.add(AgentRun(practice_id=practice.id, run_id=str(run["run_id"]), step=int(run["step"]), tool=str(run["tool"]), summary=str(run["summary"])))
    action = _create_publish_action(db, practice, result["page"], str(result.get("run_id", "")))
    db.commit()
    db.refresh(practice)

    return {"id": practice.id, "status": practice.status, "slug": practice.slug, "page": result["page"], "run_id": result.get("run_id"), "pending_action": _pending_action_result(action)}


@app.get("/practices/{practice_id}/agent-runs", response_model=AgentRunsOut)
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

    rows = db.query(AgentRun).filter(AgentRun.practice_id == practice_id, AgentRun.agent == "launch").order_by(AgentRun.step.asc()).all()
    return {"items": [{"run_id": row.run_id, "step": row.step, "tool": row.tool, "summary": row.summary, "created_at": row.created_at.isoformat()} for row in rows]}


@app.post("/demo/safety-check")
def demo_safety_check(text: str) -> dict[str, object]:
    result = risk_scan(text)
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


# ---------- 4b: session notes, assessments, case plans, copilot (therapist of the client only) ----------

def _therapist_booking(db: Session, booking_id: int, user: User) -> tuple[Booking, TherapistProfile]:
    if user.role != UserRole.therapist:
        raise HTTPException(status_code=403, detail="Access denied")
    booking, _, profile = _booking_for_participant(db, booking_id, user)
    return booking, profile


def _session_payload(row: TherapySession) -> dict[str, object]:
    return {"id": row.id, "booking_id": row.booking_id, "client_id": row.client_id, "source": row.note_source,
            "raw_notes": row.raw_notes, "structured": row.structured_json, "structured_status": row.structured_status,
            "risk_flag": row.risk_flag, "updated_at": row.updated_at.isoformat()}


@app.put("/bookings/{booking_id}/session-notes", response_model=SessionNotesOut)
def save_session_notes(
    booking_id: int,
    payload: SessionNotesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    booking, profile = _therapist_booking(db, booking_id, current_user)
    row = db.query(TherapySession).filter(TherapySession.booking_id == booking.id).first()
    if row is None:
        row = TherapySession(booking_id=booking.id, client_id=booking.client_id, therapist_user_id=current_user.id)
    row.raw_notes = payload.raw_notes
    row.note_source = payload.source
    row.structured_json = None  # any AI structuring is stale once notes change
    row.structured_status = "none"
    row.updated_at = datetime.now(timezone.utc)
    risk = scan_client_text(payload.raw_notes)  # transcripts contain client speech
    row.risk_flag = bool(risk)
    db.add(row)
    db.flush()
    index_session_notes(db, current_user, booking.client_id, row.id, payload.raw_notes)
    if risk:
        raise_risk_alert(db, therapist_user_id=current_user.id, client_id=booking.client_id,
                         source="session_notes", source_id=row.id, match=risk["match"], text=risk["text"])
    db.commit()
    return _session_payload(row) | {"safety": {"flagged": bool(risk), "message": risk["message"] if risk else None}}


@app.get("/bookings/{booking_id}/session-notes", response_model=SessionNotesOut)
def get_session_notes(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    booking, _ = _therapist_booking(db, booking_id, current_user)
    row = db.query(TherapySession).filter(TherapySession.booking_id == booking.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Session notes not found")
    return _session_payload(row)


@app.post("/clients/{client_id}/assessments", response_model=AssessmentOut)
def record_assessment(
    client_id: int,
    payload: AssessmentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_therapist_of_client),
) -> dict[str, object]:
    try:
        total = assessment_total(payload.type, payload.item_scores)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = Assessment(client_id=client_id, recorded_by=current_user.id, type=payload.type,
                     item_scores=payload.item_scores, total=total,
                     taken_at=payload.taken_at or datetime.now(timezone.utc))
    db.add(row)
    db.flush()
    flagged = phq9_item9_positive(payload.type, payload.item_scores)
    if flagged:
        raise_risk_alert(db, therapist_user_id=current_user.id, client_id=client_id,
                         source="phq9_item9", source_id=row.id, match="PHQ-9 item 9 > 0")
    db.commit()
    return {"id": row.id, "type": row.type, "total": row.total, "item_scores": row.item_scores,
            "taken_at": row.taken_at.isoformat(), "risk_alert": flagged}


@app.get("/clients/{client_id}/assessments", response_model=AssessmentsOut)
def list_assessments(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_therapist_of_client),
) -> dict[str, object]:
    rows = db.query(Assessment).filter(Assessment.client_id == client_id).order_by(Assessment.taken_at.asc()).all()
    return {"items": [{"id": r.id, "type": r.type, "total": r.total, "item_scores": r.item_scores,
                       "taken_at": r.taken_at.isoformat()} for r in rows]}


def _plan_payload(db: Session, row: CasePlan) -> dict[str, object]:
    return {"id": row.id, "client_id": row.client_id, "version": row.version, "approach": row.approach,
            "formulation_text": row.formulation_text, "goals": row.goals_json,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "created_at": row.created_at.isoformat(), "update_notes": row.update_notes,
            "update_notes_label": _notes_label(db, row.update_notes_approved_by, row.update_notes_approved_at)}


@app.post("/clients/{client_id}/case-plans", response_model=CasePlanOut)
def create_case_plan_version(
    client_id: int,
    payload: CasePlanIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_therapist_of_client),
) -> dict[str, object]:
    """Formulation is written by the therapist; each save is a new immutable version."""
    latest = (db.query(CasePlan).filter(CasePlan.client_id == client_id, CasePlan.therapist_user_id == current_user.id)
              .order_by(CasePlan.version.desc()).with_for_update().first())
    row = CasePlan(client_id=client_id, therapist_user_id=current_user.id, version=(latest.version + 1) if latest else 1,
                   approach=payload.approach, formulation_text=payload.formulation_text,
                   goals_json=[g.model_dump() for g in payload.goals],
                   approved_at=datetime.now(timezone.utc) if payload.approve else None,
                   **({"update_notes": latest.update_notes, "update_notes_approved_by": latest.update_notes_approved_by,
                       "update_notes_approved_at": latest.update_notes_approved_at} if latest else {}))
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Case plan version conflict; retry") from exc
    return _plan_payload(db, row)


@app.post("/clients/{client_id}/case-plans/{plan_id}/approve", response_model=CasePlanOut)
def approve_case_plan(
    client_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_therapist_of_client),
) -> dict[str, object]:
    row = db.query(CasePlan).filter(CasePlan.id == plan_id, CasePlan.client_id == client_id,
                                    CasePlan.therapist_user_id == current_user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Case plan not found")
    if row.approved_at is None:
        row.approved_at = datetime.now(timezone.utc)
        db.commit()
    return _plan_payload(db, row)


@app.get("/clients/{client_id}/case-plans", response_model=CasePlansOut)
def list_case_plans(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_therapist_of_client),
) -> dict[str, object]:
    rows = (db.query(CasePlan).filter(CasePlan.client_id == client_id, CasePlan.therapist_user_id == current_user.id)
            .order_by(CasePlan.version.desc()).all())
    return {"items": [_plan_payload(db, r) for r in rows]}


@app.post("/therapists/me/prepare-my-day", response_model=PrepareDayOut)
def prepare_my_day_endpoint(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    try:
        return {"items": prepare_my_day(db, current_user, hours=hours)}
    except CopilotError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/therapist/overnight-check", response_model=OvernightOut)
def overnight_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    try:
        return run_overnight_check(db, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/therapists/me/briefings", response_model=BriefingsOut)
def list_briefings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    rows = (db.query(CopilotBriefing).filter(CopilotBriefing.therapist_user_id == current_user.id)
            .order_by(CopilotBriefing.created_at.desc()).limit(50).all())
    return {"items": [{"id": r.id, "client_id": r.client_id, "status": r.status, "run_id": r.run_id,
                       "briefing": r.briefing_json, "created_at": r.created_at.isoformat()} for r in rows]}


@app.get("/therapists/me/pending-actions", response_model=TherapistActionsOut)
def therapist_pending_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    rows = (db.query(PendingAction).filter(PendingAction.assignee_user_id == current_user.id,
                                           PendingAction.type.in_(THERAPIST_ACTION_TYPES))
            .order_by(PendingAction.created_at.desc()).all())
    return {"items": [_pending_action_result(r) | {"payload": r.payload} | _action_preview(db, r) for r in rows]}


@app.get("/therapists/me/alerts", response_model=AlertsOut)
def therapist_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    rows = (db.query(Alert).filter(Alert.therapist_user_id == current_user.id)
            .order_by(Alert.acknowledged.asc(), Alert.created_at.desc()).all())
    return {"items": [{"id": r.id, "client_id": r.client_id, "type": r.type, "priority": r.priority,
                       "payload": r.payload, "acknowledged": r.acknowledged,
                       "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
                       "created_at": r.created_at.isoformat()}
                      for r in rows]}


@app.post("/alerts/{alert_id}/acknowledge", response_model=AlertItem)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    alert = db.query(Alert).filter(Alert.id == alert_id).with_for_update().first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.therapist_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    replay = alert.acknowledged
    if not replay:
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
    db.add(AuditLog(action="alert.acknowledge", actor_id=current_user.id, entity_type="alert", entity_id=alert.id,
                    details={"type": alert.type, "idempotent_replay": replay}))
    db.commit()
    return {"id": alert.id, "client_id": alert.client_id, "type": alert.type, "priority": alert.priority,
            "payload": alert.payload, "acknowledged": alert.acknowledged,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "created_at": alert.created_at.isoformat()}


@app.get("/therapists/me/agent-runs", response_model=AgentRunsOut)
def therapist_agent_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    rows = (db.query(AgentRun).filter(AgentRun.actor_user_id == current_user.id,
                                         AgentRun.agent.in_(("copilot", "monitor")))
            .order_by(AgentRun.created_at.desc(), AgentRun.step.asc()).limit(200).all())
    return {"items": [{"run_id": r.run_id, "step": r.step, "tool": r.tool, "summary": r.summary,
                       "created_at": r.created_at.isoformat()} for r in rows]}
