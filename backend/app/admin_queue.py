"""Admin verification queue and per-subject audit history. Review decisions themselves live next to each subject
(`/admin/therapists/{id}/review`, `/admin/practices/{id}/review`)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.auth import require_roles
from backend.app.db import get_db
from backend.app.models import (
    AuditLog,
    Practice,
    TherapistEducation,
    TherapistLicense,
    TherapistProfile,
    User,
    UserRole,
    VerificationDocument,
)
from backend.app.practice_setup import missing_details
from backend.app.verification import OWNER_TYPE, PRACTICE_OWNER_TYPE

router = APIRouter(tags=["admin"])
admin_only = require_roles(UserRole.admin)

QueueStatus = Literal["submitted", "changes_requested", "rejected", "verified"]
THERAPIST_ENTITY, PRACTICE_ENTITY = "therapist_profile", "practice"


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class CompletenessItem(_Out):
    label: str
    ok: bool
    count: int | None = None


class QueueItem(_Out):
    id: int
    name: str
    city: str | None = None
    verification_status: str
    submitted_at: datetime | None = None
    completeness: list[CompletenessItem]


class QueueOut(_Out):
    items: list[QueueItem]


class AuditItem(_Out):
    id: int
    action: str
    actor_name: str | None = None
    actor_role: str | None = None
    decision: str | None = None
    note: str | None = None
    created_at: datetime


class AuditOut(_Out):
    items: list[AuditItem]


def _counts(db: Session, model, column, ids: list[int], *extra) -> dict[int, int]:
    if not ids:
        return {}
    rows = db.execute(select(column, func.count()).where(column.in_(ids), *extra).group_by(column)).all()
    return {key: n for key, n in rows}


@router.get("/admin/verification-queue", response_model=QueueOut)
def verification_queue(subject: Literal["therapist", "practice"] = "therapist", status: QueueStatus = "submitted",
                       db: Session = Depends(get_db), _: User = Depends(admin_only)):
    order = (Practice.submitted_at if subject == "practice" else TherapistProfile.submitted_at).asc().nulls_last()
    items: list[dict] = []
    if subject == "therapist":
        rows = db.execute(select(TherapistProfile, User, Practice).join(User, User.id == TherapistProfile.user_id)
                          .outerjoin(Practice, Practice.id == TherapistProfile.practice_id)
                          .where(TherapistProfile.verification_status == status).order_by(order, TherapistProfile.id)).all()
        ids = [p.id for p, _, _ in rows]
        edu = _counts(db, TherapistEducation, TherapistEducation.therapist_id, ids)
        lic = _counts(db, TherapistLicense, TherapistLicense.therapist_id, ids)
        docs = _counts(db, VerificationDocument, VerificationDocument.owner_id, ids, VerificationDocument.owner_type == OWNER_TYPE)
        for p, u, pr in rows:
            comp = [("Education", edu.get(p.id, 0)), ("Licences", lic.get(p.id, 0)), ("Documents", docs.get(p.id, 0))]
            items.append({"id": p.id, "name": u.name, "city": pr.city if pr else None, "verification_status": p.verification_status,
                          "submitted_at": p.submitted_at,
                          "completeness": [{"label": label, "ok": n > 0, "count": n} for label, n in comp]})
    else:
        rows = db.scalars(select(Practice).where(Practice.verification_status == status).order_by(order, Practice.id)).all()
        ids = [p.id for p in rows]
        docs = _counts(db, VerificationDocument, VerificationDocument.owner_id, ids, VerificationDocument.owner_type == PRACTICE_OWNER_TYPE)
        team = _counts(db, TherapistProfile, TherapistProfile.practice_id, ids, TherapistProfile.left_practice_at.is_(None))
        for p in rows:
            comp = [{"label": "Details complete", "ok": not missing_details(p), "count": None},
                    {"label": "Documents", "ok": docs.get(p.id, 0) > 0, "count": docs.get(p.id, 0)},
                    {"label": "Team", "ok": team.get(p.id, 0) > 0, "count": team.get(p.id, 0)},
                    {"label": "Page text saved", "ok": bool((p.page_text or "").strip()), "count": None}]
            items.append({"id": p.id, "name": p.name, "city": p.city, "verification_status": p.verification_status,
                          "submitted_at": p.submitted_at, "completeness": comp})
    return {"items": items}


def _history(db: Session, entity_type: str, entity_id: int) -> dict:
    rows = db.execute(select(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_id)
                      .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
                      .order_by(AuditLog.id.desc())).all()
    return {"items": [{"id": a.id, "action": a.action, "actor_name": u.name if u else None,
                       "actor_role": str(getattr(u.role, "value", u.role)) if u else None, "decision": (a.details or {}).get("decision"),
                       "note": a.note, "created_at": a.created_at} for a, u in rows]}


@router.get("/admin/therapists/{therapist_id}/audit", response_model=AuditOut)
def therapist_audit(therapist_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    if db.get(TherapistProfile, therapist_id) is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    return _history(db, THERAPIST_ENTITY, therapist_id)


@router.get("/admin/practices/{practice_id}/audit", response_model=AuditOut)
def practice_audit(practice_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    if db.get(Practice, practice_id) is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return _history(db, PRACTICE_ENTITY, practice_id)
