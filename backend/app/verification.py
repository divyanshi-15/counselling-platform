"""Therapist credentials and verification: profile edits, education, licenses, private documents, review.

Documents live on a private volume under random keys and are served only through `download_document`
(the owning therapist and admins). License numbers are returned only to the owner and admins, never publicly.
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_roles
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
from backend.app.schemas import TherapistProfileOut

router = APIRouter(tags=["verification"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_DOCS_PER_THERAPIST = 10
DOC_TYPES = ("degree_certificate", "registration_certificate", "identity_proof", "other")
EDITABLE_DOC_STATES = ("draft", "changes_requested")
OWNER_TYPE = "therapist"
PRACTICE_OWNER_TYPE = "practice"
FIRST_YEAR = 1950

# content signature -> (content type, allowed filename extensions)
_SIGNATURES = (
    (b"%PDF-", "application/pdf", (".pdf",)),
    (b"\xff\xd8\xff", "image/jpeg", (".jpg", ".jpeg")),
    (b"\x89PNG\r\n\x1a\n", "image/png", (".png",)),
)


def upload_dir() -> Path:
    """Private volume (docker-compose `uploads`); never mounted into the web server's static root."""
    return Path(os.getenv("UPLOAD_DIR", "/data/uploads")) / "verification"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _year_ok(year: int) -> int:
    if not FIRST_YEAR <= year <= date.today().year:
        raise ValueError("Enter a valid year")
    return year


# ---------- schemas ----------

class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ProfileUpdateIn(_In):
    bio: str | None = Field(default=None, max_length=2000)
    languages: list[Literal["en", "hi"]] | None = Field(default=None, min_length=1, max_length=2)
    specialisations: list[Annotated[str, Field(min_length=1, max_length=60)]] | None = Field(default=None, max_length=10)
    fee: int | None = Field(default=None, gt=0, le=100000)
    years_experience: int | None = Field(default=None, ge=0, le=60)


class EducationIn(_In):
    degree: str = Field(min_length=1, max_length=150)
    institution: str = Field(min_length=1, max_length=200)
    year: int

    @model_validator(mode="after")
    def _check(self):
        _year_ok(self.year)
        return self


class LicenseIn(_In):
    license_type: str = Field(min_length=1, max_length=100)
    registration_body: str = Field(min_length=1, max_length=150)
    registration_number: str = Field(min_length=1, max_length=60)
    issue_year: int
    valid_until: date | None = None

    @model_validator(mode="after")
    def _check(self):
        _year_ok(self.issue_year)
        if self.valid_until is not None and self.valid_until.year < self.issue_year:
            raise ValueError("valid_until cannot be before the issue year")
        return self


class EducationOut(_Out):
    id: int
    degree: str
    institution: str
    year: int


class LicenseOut(_Out):
    id: int
    license_type: str
    registration_body: str
    registration_number: str
    issue_year: int
    valid_until: date | None = None


class DocumentOut(_Out):
    id: int
    doc_type: str
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime


class VerificationOut(_Out):
    status: str
    reviewer_note: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    missing: list[str]
    can_edit_documents: bool
    education: list[EducationOut]
    licenses: list[LicenseOut]
    documents: list[DocumentOut]


class ReviewIn(_In):
    decision: Literal["verified", "changes_requested", "rejected"]
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _check(self):
        self.note = (self.note or "").strip() or None
        if self.decision != "verified" and not self.note:
            raise ValueError("A reviewer note is required")
        return self


class ReviewOut(_Out):
    id: int
    status: str
    verified: bool
    reviewer_note: str | None = None
    reviewed_at: datetime | None = None


class AdminVerificationOut(VerificationOut):
    id: int
    name: str | None = None
    practice_name: str | None = None
    city: str | None = None
    bio: str = ""
    approaches: list[str] = []
    languages: list[str] = []
    specialisations: list[str] = []
    fee: int | None = None
    years_experience: int | None = None


# ---------- helpers ----------

def ensure_profile(db: Session, user: User) -> TherapistProfile:
    """Get or create the therapist's draft profile: no practice, unverified, never listed. Idempotent (user_id is unique)."""
    profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == user.id).first()
    if profile is None:
        try:
            with db.begin_nested():
                profile = TherapistProfile(user_id=user.id, bio="", approaches=[], languages=[], specialisations=[],
                                           verified=False, verification_status="draft")
                db.add(profile)
        except IntegrityError:  # concurrent request created it first
            profile = db.query(TherapistProfile).filter(TherapistProfile.user_id == user.id).one()
    return profile


def backfill_draft_profiles(db: Session) -> int:
    """Draft profiles for therapist users that have none; safe to run repeatedly."""
    users = db.query(User).filter(User.role == UserRole.therapist,
                                  ~db.query(TherapistProfile.id).filter(TherapistProfile.user_id == User.id).exists()).all()
    for u in users:
        ensure_profile(db, u)
    db.commit()
    return len(users)


def own_profile(db: Session, user: User) -> TherapistProfile:
    profile = ensure_profile(db, user)
    db.commit()
    return profile


def profile_dict(profile: TherapistProfile, practice_name: str | None = None) -> dict[str, object]:
    return {"id": profile.id, "practice_id": profile.practice_id, "practice_name": practice_name, "bio": profile.bio, "approaches": profile.approaches,
            "languages": profile.languages, "fee": profile.fee, "verified": profile.verified,
            "specialisations": profile.specialisations, "years_experience": profile.years_experience,
            "verification_status": profile.verification_status, "reviewer_note": profile.reviewer_note,
            "submitted_at": profile.submitted_at, "reviewed_at": profile.reviewed_at}


def _practice_name(db: Session, profile: TherapistProfile) -> str | None:
    practice = db.get(Practice, profile.practice_id) if profile.practice_id else None
    return practice.name if practice and profile.left_practice_at is None else None


def set_status(profile: TherapistProfile, status: str, note: str | None = None, *, reviewed: bool = False) -> None:
    """Single place that moves a profile between states; `verified` (what public listings read) always follows."""
    profile.verification_status = status
    profile.verified = status == "verified"
    if status == "submitted":
        profile.submitted_at = _now()
    if reviewed:
        profile.reviewed_at = _now()
        profile.reviewer_note = note


def _children(db: Session, profile: TherapistProfile):
    education = db.query(TherapistEducation).filter(TherapistEducation.therapist_id == profile.id).order_by(TherapistEducation.year.desc(), TherapistEducation.id).all()
    licenses = db.query(TherapistLicense).filter(TherapistLicense.therapist_id == profile.id).order_by(TherapistLicense.id).all()
    documents = (db.query(VerificationDocument).filter(VerificationDocument.owner_type == OWNER_TYPE,
                                                       VerificationDocument.owner_id == profile.id)
                 .order_by(VerificationDocument.id).all())
    return education, licenses, documents


def verification_summary(db: Session, profile: TherapistProfile) -> dict[str, object]:
    education, licenses, documents = _children(db, profile)
    missing = [label for label, rows in (("education", education), ("license", licenses), ("document", documents)) if not rows]
    return {"status": profile.verification_status, "reviewer_note": profile.reviewer_note,
            "submitted_at": profile.submitted_at, "reviewed_at": profile.reviewed_at, "missing": missing,
            "can_edit_documents": profile.verification_status in EDITABLE_DOC_STATES,
            "education": education, "licenses": licenses, "documents": documents}


def _require_credentials_editable(profile: TherapistProfile) -> None:
    if profile.verification_status in ("submitted", "rejected"):
        raise HTTPException(status_code=409, detail=f"Credentials cannot be changed while the profile is {profile.verification_status}")


def _license_changed(db: Session, profile: TherapistProfile) -> None:
    """A verified therapist who touches license details goes back to review and leaves the public listing."""
    if profile.verification_status == "verified":
        set_status(profile, "submitted")


def sniff(data: bytes, filename: str) -> str:
    """Content type from the bytes themselves; the filename extension must agree, the client's Content-Type is ignored."""
    ext = os.path.splitext(filename.lower())[1]
    for magic, content_type, exts in _SIGNATURES:
        if data.startswith(magic):
            if ext not in exts:
                break
            return content_type
    raise HTTPException(status_code=415, detail="Only PDF, JPG or PNG files are accepted")


def clean_filename(name: str) -> str:
    base = re.sub(r"[^\w.\- ()]", "_", name.replace("\\", "/").rsplit("/", 1)[-1]).strip(" .") or "document"
    stem, ext = os.path.splitext(base)
    return stem[:100] + ext[:10]


def store_file(db: Session, owner_type: str, owner_id: int, doc_type: str, filename: str, data: bytes) -> VerificationDocument:
    """Validate, write under a random key, add the row (caller commits). Shared by therapist and practice uploads and the seed."""
    content_type = sniff(data, filename)
    key = secrets.token_hex(16)
    path = upload_dir() / key
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    doc = VerificationDocument(owner_type=owner_type, owner_id=owner_id, doc_type=doc_type,
                               filename=clean_filename(filename), content_type=content_type, size=len(data),
                               storage_key=key)
    db.add(doc)
    return doc


def store_document(db: Session, profile: TherapistProfile, doc_type: str, filename: str, data: bytes) -> VerificationDocument:
    return store_file(db, OWNER_TYPE, profile.id, doc_type, filename, data)


def read_upload(request: Request, file: UploadFile) -> bytes:
    """Size and emptiness checks shared by every document upload endpoint."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + 64 * 1024:
        raise HTTPException(status_code=413, detail="File is larger than 5 MB")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 5 MB")
    if not data:
        raise HTTPException(status_code=422, detail="File is empty")
    return data


def _audit(db: Session, actor: User, action: str, profile: TherapistProfile, *, note: str | None = None, **details: object) -> None:
    db.add(AuditLog(action=action, actor_id=actor.id, entity_type="therapist_profile", entity_id=profile.id, details=details, note=note))


# ---------- therapist: profile ----------

@router.patch("/therapists/me/profile", response_model=TherapistProfileOut)
def update_profile(payload: ProfileUpdateIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(UserRole.therapist))) -> dict[str, object]:
    profile = own_profile(db, user)
    changes = payload.model_dump(exclude_unset=True)
    if any(v is None for v in changes.values()):
        raise HTTPException(status_code=422, detail="Fields cannot be null")
    for field, value in changes.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile_dict(profile, _practice_name(db, profile))


@router.get("/therapists/me/verification", response_model=VerificationOut)
def my_verification(db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    return verification_summary(db, own_profile(db, user))


# ---------- therapist: education ----------

def _owned(db: Session, model, row_id: int, profile: TherapistProfile):
    row = db.get(model, row_id)
    if row is None or row.therapist_id != profile.id:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.post("/therapists/me/education", response_model=EducationOut, status_code=201)
def add_education(payload: EducationIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_credentials_editable(profile)
    row = TherapistEducation(therapist_id=profile.id, **payload.model_dump())
    db.add(row)
    db.commit()
    return row


@router.put("/therapists/me/education/{item_id}", response_model=EducationOut)
def update_education(item_id: int, payload: EducationIn, db: Session = Depends(get_db),
                     user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_credentials_editable(profile)
    row = _owned(db, TherapistEducation, item_id, profile)
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    db.commit()
    return row


@router.delete("/therapists/me/education/{item_id}", status_code=204, response_class=Response)
def delete_education(item_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_credentials_editable(profile)
    row = _owned(db, TherapistEducation, item_id, profile)
    if profile.verification_status != "draft" and db.query(TherapistEducation).filter(TherapistEducation.therapist_id == profile.id).count() <= 1:
        raise HTTPException(status_code=409, detail="Keep at least one education entry once submitted")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


# ---------- therapist: licenses ----------

@router.post("/therapists/me/licenses", response_model=LicenseOut, status_code=201)
def add_license(payload: LicenseIn, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_credentials_editable(profile)
    row = TherapistLicense(therapist_id=profile.id, **payload.model_dump())
    db.add(row)
    _license_changed(db, profile)
    db.commit()
    return row


@router.put("/therapists/me/licenses/{item_id}", response_model=LicenseOut)
def update_license(item_id: int, payload: LicenseIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_credentials_editable(profile)
    row = _owned(db, TherapistLicense, item_id, profile)
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    _license_changed(db, profile)
    db.commit()
    return row


@router.delete("/therapists/me/licenses/{item_id}", status_code=204, response_class=Response)
def delete_license(item_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_credentials_editable(profile)
    row = _owned(db, TherapistLicense, item_id, profile)
    if profile.verification_status != "draft" and db.query(TherapistLicense).filter(TherapistLicense.therapist_id == profile.id).count() <= 1:
        raise HTTPException(status_code=409, detail="Keep at least one license once submitted")
    db.delete(row)
    _license_changed(db, profile)
    db.commit()
    return Response(status_code=204)


# ---------- therapist: documents ----------

def _require_docs_editable(profile: TherapistProfile) -> None:
    if profile.verification_status not in EDITABLE_DOC_STATES:
        raise HTTPException(status_code=409, detail="Documents can only be changed while the profile is a draft or changes are requested")


@router.post("/therapists/me/documents", response_model=DocumentOut, status_code=201)
def upload_document(request: Request, doc_type: Annotated[str, Form()], file: Annotated[UploadFile, File()],
                    db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    _require_docs_editable(profile)
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=422, detail="Unknown document type")
    data = read_upload(request, file)
    count = db.query(VerificationDocument).filter(VerificationDocument.owner_type == OWNER_TYPE,
                                                  VerificationDocument.owner_id == profile.id).count()
    if count >= MAX_DOCS_PER_THERAPIST:
        raise HTTPException(status_code=409, detail=f"At most {MAX_DOCS_PER_THERAPIST} documents")
    doc = store_document(db, profile, doc_type, file.filename or "document", data)
    try:
        db.commit()
    except Exception:
        (upload_dir() / doc.storage_key).unlink(missing_ok=True)
        raise
    return doc


@router.delete("/therapists/me/documents/{doc_id}", status_code=204, response_class=Response)
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    doc = db.get(VerificationDocument, doc_id)
    if doc is None or doc.owner_type != OWNER_TYPE or doc.owner_id != profile.id:
        raise HTTPException(status_code=404, detail="Not found")
    _require_docs_editable(profile)
    key = doc.storage_key
    db.delete(doc)
    db.commit()
    (upload_dir() / key).unlink(missing_ok=True)
    return Response(status_code=204)


@router.get("/verification-documents/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db),
                      user: User = Depends(require_roles(UserRole.therapist, UserRole.practice_owner, UserRole.admin))):
    """Therapist documents: that therapist and admins. Practice documents: that practice's owner and admins.
    A role that never owns that kind of document gets 403; the wrong therapist or owner gets 404."""
    doc = db.get(VerificationDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    kind_role = {OWNER_TYPE: UserRole.therapist, PRACTICE_OWNER_TYPE: UserRole.practice_owner}.get(doc.owner_type)
    if user.role != UserRole.admin and user.role != kind_role:
        raise HTTPException(status_code=403, detail="Access denied")
    profile = practice = None
    if doc.owner_type == OWNER_TYPE:
        profile = db.get(TherapistProfile, doc.owner_id)
        allowed = profile is not None and user.role == UserRole.therapist and profile.user_id == user.id
    elif doc.owner_type == PRACTICE_OWNER_TYPE:
        practice = db.get(Practice, doc.owner_id)
        allowed = practice is not None and user.role == UserRole.practice_owner and practice.owner_id == user.id
    else:
        allowed = False
    if user.role != UserRole.admin and not allowed:
        raise HTTPException(status_code=404, detail="Not found")
    path = upload_dir() / doc.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File is no longer available")
    if user.role == UserRole.admin:
        entity = profile or practice
        if entity is not None:
            db.add(AuditLog(action="verification_document.download", actor_id=user.id,
                            entity_type="therapist_profile" if profile is not None else "practice", entity_id=entity.id,
                            details={"document_id": doc.id}))
            db.commit()
    return FileResponse(path, media_type=doc.content_type, filename=doc.filename,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


# ---------- therapist: submit ----------

@router.post("/therapists/me/verification/submit", response_model=VerificationOut)
def submit_verification(db: Session = Depends(get_db), user: User = Depends(require_roles(UserRole.therapist))):
    profile = own_profile(db, user)
    if profile.verification_status not in EDITABLE_DOC_STATES:
        raise HTTPException(status_code=409, detail=f"A {profile.verification_status} profile cannot be submitted")
    summary = verification_summary(db, profile)
    if summary["missing"]:
        raise HTTPException(status_code=422, detail="Add at least one education entry, license and document before submitting: missing "
                            + ", ".join(summary["missing"]))
    set_status(profile, "submitted")
    _audit(db, user, "therapist.verification_submit", profile)
    db.commit()
    return verification_summary(db, profile)


# ---------- admin ----------

@router.get("/admin/therapists/{therapist_id}/verification", response_model=AdminVerificationOut)
def admin_verification(therapist_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.admin))):
    profile = db.get(TherapistProfile, therapist_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    owner = db.get(User, profile.user_id)
    practice = db.get(Practice, profile.practice_id) if profile.practice_id else None
    return {"id": profile.id, "name": owner.name if owner else None,
            "practice_name": practice.name if practice else None, "city": practice.city if practice else None,
            "bio": profile.bio, "approaches": profile.approaches or [], "languages": profile.languages or [],
            "specialisations": profile.specialisations or [], "fee": profile.fee, "years_experience": profile.years_experience,
            **verification_summary(db, profile)}


@router.post("/admin/therapists/{therapist_id}/review", response_model=ReviewOut)
def review_therapist(therapist_id: int, payload: ReviewIn, db: Session = Depends(get_db),
                     admin: User = Depends(require_roles(UserRole.admin))):
    profile = db.get(TherapistProfile, therapist_id, with_for_update=True)
    if profile is None:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    if profile.verification_status == payload.decision:
        pass  # repeat of the decision already taken: same answer, no second audit row
    elif profile.verification_status != "submitted":
        raise HTTPException(status_code=409, detail="Only a submitted profile can be reviewed")
    else:
        set_status(profile, payload.decision, payload.note, reviewed=True)
        _audit(db, admin, "therapist.review", profile, note=payload.note, decision=payload.decision)
        db.commit()
    return {"id": profile.id, "status": profile.verification_status, "verified": profile.verified,
            "reviewer_note": profile.reviewer_note, "reviewed_at": profile.reviewed_at}
