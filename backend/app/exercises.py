"""Exercise runner. NOT an agent: no model calls anywhere in this module. Fixed templates, two tools only:
save_checkin and flag_risk. Every client response carries the fixed notice."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_roles
from backend.app.clinical import raise_risk_alert, scan_client_text
from backend.app.db import get_db
from backend.app.models import Alert, Assignment, Checkin, Exercise, User, UserRole
from backend.app.ratelimit import client_rate_limit
from backend.app.safety import CRISIS_MESSAGE

RUNNER_TOOLS = ("save_checkin", "flag_risk")
NOTICE = "Skill-building support, not a replacement for therapy."
CRISIS_LINE = "If you are in crisis, call Tele-MANAS 14416 (or 1-800-891-4416) or your local emergency number."
LANGS = {"en", "hi", "kn"}

router = APIRouter()
client_only = require_roles(UserRole.client)


def with_notice(body: dict[str, Any]) -> dict[str, Any]:
    return body | {"notice": NOTICE, "crisis_line": CRISIS_LINE}


class CheckinIn(BaseModel):
    responses: dict[str, str | int] = Field(default_factory=dict)


def template_for(exercise: Exercise, lang: str = "en") -> tuple[str, dict]:
    if lang == "hi" and exercise.template_hi:
        return exercise.title_hi or exercise.title_en, exercise.template_hi
    if lang == "kn" and exercise.template_kn:
        return exercise.title_kn or exercise.title_en, exercise.template_kn
    return exercise.title_en, exercise.template_en


def approved_exercises(db: Session, client_id: int) -> list[dict[str, Any]]:
    rows = (db.query(Assignment, Exercise).join(Exercise, Exercise.id == Assignment.exercise_id)
            .filter(Assignment.client_id == client_id).order_by(Assignment.created_at.desc(), Assignment.id.desc()).all())
    return [{"assignment_id": a.id, "exercise": e.slug, "title": e.title_en, "status": a.status,
             "assigned_at": a.created_at.isoformat()} for a, e in rows]


def _own_assignment(db: Session, assignment_id: int, user: User) -> tuple[Assignment, Exercise]:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    if a.client_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return a, db.get(Exercise, a.exercise_id)


def _validate_responses(template: dict, responses: dict[str, str | int]) -> dict[str, str | int]:
    fields = {f["id"]: f for f in template["fields"]}
    if set(responses) - set(fields):
        raise HTTPException(status_code=422, detail="Responses must match the exercise fields")
    clean: dict[str, str | int] = {}
    for fid, field in fields.items():
        value = responses.get(fid)
        empty = value is None or (isinstance(value, str) and not value.strip())
        if empty:
            if field.get("required"):
                raise HTTPException(status_code=422, detail=f"'{field['label']}' is required")
            continue
        if field["type"] == "scale":
            try:
                number = int(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"'{field['label']}' needs a number from 0 to 10") from None
            if not 0 <= number <= 10:
                raise HTTPException(status_code=422, detail=f"'{field['label']}' needs a number from 0 to 10")
            clean[fid] = number
        else:
            text = str(value).strip()
            if len(text) > 2000:
                raise HTTPException(status_code=422, detail=f"'{field['label']}' is too long")
            clean[fid] = text
    return clean


# ---------- the runner's only two tools ----------

def save_checkin(db: Session, assignment: Assignment, responses: dict[str, str | int], flagged: bool = False) -> Checkin:
    row = Checkin(assignment_id=assignment.id, responses_json=responses, flagged=flagged)
    db.add(row)
    if not flagged:
        assignment.status = "completed"
    return row


def flag_risk(db: Session, assignment: Assignment, hit: dict) -> Alert:
    return raise_risk_alert(db, therapist_user_id=assignment.therapist_user_id, client_id=assignment.client_id,
                            source="checkin", source_id=assignment.id, match=hit["match"], text=hit["text"])


# ---------- endpoints ----------

@router.get("/client/assignments", dependencies=[Depends(client_rate_limit)])
def list_my_assignments(db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    return with_notice({"items": approved_exercises(db, user.id)})


@router.get("/client/assignments/{assignment_id}/exercise", dependencies=[Depends(client_rate_limit)])
def get_exercise_template(assignment_id: int, lang: str = Query(default="en"), db: Session = Depends(get_db),
                          user: User = Depends(client_only)) -> dict[str, Any]:
    a, exercise = _own_assignment(db, assignment_id, user)
    title, template = template_for(exercise, lang if lang in LANGS else "en")
    return with_notice({"assignment_id": a.id, "exercise": exercise.slug, "title": title, "status": a.status,
                        "template": template})


@router.post("/client/assignments/{assignment_id}/checkin", dependencies=[Depends(client_rate_limit)])
def submit_checkin(assignment_id: int, payload: CheckinIn, db: Session = Depends(get_db),
                   user: User = Depends(client_only)) -> dict[str, Any]:
    a, exercise = _own_assignment(db, assignment_id, user)
    hit = scan_client_text(payload.responses)  # runs before validation or saving; no model involved
    if hit:
        save_checkin(db, a, payload.responses, flagged=True)  # raw, unvalidated: the therapist sees what was written
        db.flush()
        flag_risk(db, a, hit)
        db.commit()
        return with_notice({"status": "crisis", "message": CRISIS_MESSAGE})
    responses = _validate_responses(exercise.template_en, payload.responses)
    row = save_checkin(db, a, responses)
    db.commit()
    return with_notice({"status": "saved", "checkin_id": row.id, "completed_at": row.completed_at.isoformat()})
