from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Computed, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str):
    client = "client"
    therapist = "therapist"
    practice_owner = "practice_owner"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.client)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)


class Practice(Base):
    __tablename__ = "practices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    page_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    # verification: `verified` (what public listings read) always follows verification_status
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # structured details the owner edits
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    approach: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialisations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    session_formats: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    fee_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fee_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_operating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # editable page draft (AI proposes, the owner edits; publishing copies it into page_json)
    page_tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    page_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_source: Mapped[str | None] = mapped_column(String(16), nullable=True)  # ai | edited | manual
    page_inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    page_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # custom domain the owner confirmed (pointed at the Saarthi server; booking stays inside Saarthi)
    custom_domain: Mapped[str | None] = mapped_column(String(253), nullable=True, unique=True, index=True)
    domain_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PracticeInvite(Base):
    """Therapist invitation. Only a hash of the single-use token is stored; the token itself exists only in the email."""

    __tablename__ = "practice_invites"
    __table_args__ = (UniqueConstraint("practice_id", "idempotency_key", name="uq_practice_invite_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practices.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class TherapistProfile(Base):
    __tablename__ = "therapist_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    practice_id: Mapped[int] = mapped_column(ForeignKey("practices.id", ondelete="CASCADE"), nullable=False, index=True)
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    approaches: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fee: Mapped[int] = mapped_column(Integer, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    credentials: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    years_experience: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    specialisations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # set when the practice owner removes them from the team: unlisted and unbookable, existing care is untouched
    left_practice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TherapistEducation(Base):
    __tablename__ = "therapist_education"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("therapist_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    degree: Mapped[str] = mapped_column(String(150), nullable=False)
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)


class TherapistLicense(Base):
    __tablename__ = "therapist_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("therapist_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    license_type: Mapped[str] = mapped_column(String(100), nullable=False)
    registration_body: Mapped[str] = mapped_column(String(150), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(60), nullable=False)
    issue_year: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class VerificationDocument(Base):
    """Private credential file. owner_type/owner_id is polymorphic ('therapist' + therapist_profiles.id, 'practice' + practices.id);
    bytes live on a private volume under a random storage_key and are served only by an authenticated endpoint."""

    __tablename__ = "verification_documents"
    __table_args__ = (Index("ix_verification_documents_owner", "owner_type", "owner_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (UniqueConstraint("therapist_id", "starts_at", "ends_at", name="uq_availability_therapist_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("therapist_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    availability_slot_id: Mapped[int] = mapped_column(
        ForeignKey("availability_slots.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    room_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class IntakeForm(Base):
    __tablename__ = "intake_forms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    therapist_id: Mapped[int] = mapped_column(
        ForeignKey("therapist_profiles.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    fields_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class IntakeResponse(Base):
    __tablename__ = "intake_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    answers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    practice_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    # Clinical actions are decided by this therapist only; practice owners only see publish_page.
    assignee_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    practice_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    agent: Mapped[str] = mapped_column(String(32), nullable=False, default="launch", server_default="launch")
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    input_short: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    high_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    email_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")  # pending | sent | failed | not_configured | skipped
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


EMBEDDING_DIM = 384


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    approach: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    source_inspired_by: Mapped[str] = mapped_column(Text, nullable=False)
    licence: Mapped[str] = mapped_column(String(100), nullable=False, default="original, for demo")
    reviewed_by: Mapped[str] = mapped_column(String(150), nullable=False, default="UNREVIEWED")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        Index("ix_kb_chunks_approach_language", "approach", "language"),
        Index("ix_kb_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    approach: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    topic_tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))


class CaseMemoryChunk(Base):
    __tablename__ = "case_memory_chunks"
    __table_args__ = (
        Index("ix_case_memory_client_therapist", "client_id", "therapist_user_id"),
        Index("ix_case_memory_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class TherapySession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    note_source: Mapped[str] = mapped_column(String(16), nullable=False, default="typed")
    raw_notes: Mapped[str] = mapped_column(Text, nullable=False)
    structured_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    structured_status: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class CasePlan(Base):
    __tablename__ = "case_plans"
    __table_args__ = (UniqueConstraint("client_id", "therapist_user_id", "version", name="uq_case_plan_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    approach: Mapped[str] = mapped_column(String(32), nullable=False)
    formulation_text: Mapped[str] = mapped_column(Text, nullable=False)
    goals_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    # approved AI draft, never merged into formulation_text
    update_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_notes_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    update_notes_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    item_scores: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    # monitoring alerts only: "monitor:<client>:<date>:<type>"; risk alerts leave it NULL
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)


class CopilotBriefing(Base):
    __tablename__ = "copilot_briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    briefing_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Exercise(Base):
    """Fixed, hand-written library. Hindi columns are nullable; English is the fallback."""
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kb_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title_en: Mapped[str] = mapped_column(String(255), nullable=False)
    template_en: Mapped[dict] = mapped_column(JSON, nullable=False)
    title_hi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    template_hi: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False)
    # unique: one approved release action creates at most one assignment
    pending_action_id: Mapped[int] = mapped_column(ForeignKey("pending_actions.id", ondelete="CASCADE"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="assigned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Checkin(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    responses_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class MoodCheckin(Base):
    """One row per client per day (upserted). The note is client free text and went through the safety check first."""
    __tablename__ = "mood_checkins"
    __table_args__ = (UniqueConstraint("client_id", "entry_date", name="uq_mood_client_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    mood: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_hours: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class JournalEntry(Base):
    """Private by default; the therapist sees an entry only while shared is true."""
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("client_id", "idempotency_key", name="uq_journal_client_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class Journey(Base):
    """A programme: ordered weekly steps. created_by NULL = shared library template; otherwise the authoring therapist."""
    __tablename__ = "journeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    title_hi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class JourneyStep(Base):
    __tablename__ = "journey_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    journey_id: Mapped[int] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False)
    text_en: Mapped[str] = mapped_column(String(400), nullable=False)
    text_hi: Mapped[str | None] = mapped_column(String(400), nullable=True)


class JourneyAssignment(Base):
    __tablename__ = "journey_assignments"
    __table_args__ = (UniqueConstraint("client_id", "idempotency_key", name="uq_journey_assignment_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    journey_id: Mapped[int] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class JourneyStepProgress(Base):
    __tablename__ = "journey_step_progress"
    __table_args__ = (UniqueConstraint("assignment_id", "step_id", name="uq_journey_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("journey_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("journey_steps.id", ondelete="CASCADE"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ReminderPreference(Base):
    """Off by default: a row only exists once the client opts in or out."""
    __tablename__ = "reminder_preferences"

    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    daily_checkin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    exercise_nudges: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ReminderLog(Base):
    """One row per send; the unique key makes every send idempotent."""
    __tablename__ = "reminder_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
