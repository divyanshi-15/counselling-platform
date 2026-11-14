from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel as _PydBase, ConfigDict, EmailStr, Field


class BaseModel(_PydBase):
    """Request/response base: unknown fields (role, verified, owner_id...) are rejected, never ignored."""

    model_config = ConfigDict(extra="forbid")


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["client", "therapist", "practice_owner"] = "client"
    language: str = "en"
    name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    language: str
    name: str | None = None


class PracticeDraft(BaseModel):
    name: str
    location: str
    languages: list[str] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)
    approaches: list[str] = Field(default_factory=list)
    fee_range: str = "2000-3000"
    tone: str = "warm and calm"
    session_type: str = "online"
    tagline: str | None = None


class PracticeContact(BaseModel):
    name: str
    email: EmailStr
    practice: str
    message: str


class PracticeOut(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    verified: bool
    page_json: dict[str, object]


class TherapistProfileIn(BaseModel):
    practice_id: int
    bio: str = ""
    approaches: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    fee: int = Field(gt=0)


class AvailabilitySlotIn(BaseModel):
    starts_at: datetime
    ends_at: datetime


class BookingIn(BaseModel):
    availability_slot_id: int


class IntakeFormIn(BaseModel):
    fields: list[dict[str, object]] = Field(min_length=1)


class IntakeResponseIn(BaseModel):
    answers: dict[str, object]


class MessageResponse(BaseModel):
    message: str


class SessionNotesIn(BaseModel):
    raw_notes: str = Field(min_length=1, max_length=50000)
    source: Literal["typed", "transcript"] = "typed"


class AssessmentIn(BaseModel):
    type: Literal["PHQ9", "GAD7"]
    item_scores: list[int]
    taken_at: datetime | None = None


class CaseGoal(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=500)


class CasePlanIn(BaseModel):
    approach: str = Field(min_length=1, max_length=32)
    formulation_text: str = Field(min_length=1, max_length=20000)
    goals: list[CaseGoal] = Field(default_factory=list, max_length=12)
    approve: bool = False


# ---------- responses (client-facing endpoints) ----------

class _Out(_PydBase):
    model_config = ConfigDict(extra="ignore")


class Notice(_Out):
    notice: str
    crisis_line: str


class PracticeRef(_Out):
    id: int
    name: str
    slug: str


class DashboardTherapist(_Out):
    id: int
    name: str | None = None
    bio: str | None = None
    approaches: list[str] | None = None
    languages: list[str] | None = None
    fee: int | None = None
    practice: PracticeRef


class UpcomingSession(_Out):
    id: int
    starts_at: str
    ends_at: str
    status: str


class ApprovedExercise(_Out):
    assignment_id: int
    exercise: str
    title: str
    status: str
    assigned_at: str


class ClientDashboardOut(Notice):
    practice: PracticeRef | None
    therapist: DashboardTherapist | None
    upcoming_session: UpcomingSession | None
    approved_exercises: list[ApprovedExercise]


class AssignmentsOut(Notice):
    items: list[ApprovedExercise]


class TemplateField(_Out):
    model_config = ConfigDict(extra="allow")
    id: str
    label: str
    type: str | None = None
    required: bool | None = None


class ExerciseTemplate(_Out):
    model_config = ConfigDict(extra="allow")
    fields: list[TemplateField]


class ExerciseTemplateOut(Notice):
    assignment_id: int
    exercise: str
    title: str
    status: str
    template: ExerciseTemplate


class CheckinOut(Notice):
    status: Literal["saved", "crisis"]
    message: str | None = None
    checkin_id: int | None = None
    completed_at: str | None = None


class SlotOut(_Out):
    id: int
    starts_at: str
    ends_at: str


class MySlotOut(_Out):
    id: int
    starts_at: str
    ends_at: str
    booked: bool = False


class MySlotsOut(_Out):
    items: list[MySlotOut]


class AvailabilityOut(_Out):
    items: list[SlotOut]


class BookingOut(_Out):
    id: int
    status: str
    therapist_id: int
    starts_at: str
    ends_at: str
    confirmation_email: str


class IntakeField(_Out):
    model_config = ConfigDict(extra="allow")
    id: str
    label: str
    type: str | None = None
    required: bool | None = None


class IntakeFormOut(_Out):
    booking_id: int
    fields: list[IntakeField]


class IntakeSafety(_Out):
    flagged: bool
    message: str | None = None


class IntakeSubmitOut(Notice):
    id: int
    booking_id: int
    answers: dict[str, object]
    submitted_at: str
    safety: IntakeSafety


class IntakeResponseOut(_Out):
    id: int
    booking_id: int
    client_id: int
    answers: dict[str, object]
    submitted_at: str


class RoomOut(_Out):
    room_name: str


# ---------- responses (therapist-facing endpoints) ----------

class TherapistProfileOut(_Out):
    id: int
    practice_id: int
    bio: str | None = None
    approaches: list[str] | None = None
    languages: list[str] | None = None
    fee: int | None = None
    verified: bool


class PersonRef(_Out):
    id: int
    name: str | None = None


class TherapistBookingItem(_Out):
    id: int
    status: str
    starts_at: str
    ends_at: str
    client: PersonRef


class TherapistBookingsOut(_Out):
    items: list[TherapistBookingItem]


class SessionSafety(_Out):
    flagged: bool
    message: str | None = None


class SessionNotesOut(_Out):
    id: int
    booking_id: int
    client_id: int
    source: str
    raw_notes: str
    structured: dict[str, object] | None = None
    structured_status: str
    risk_flag: bool
    updated_at: str
    safety: SessionSafety | None = None


class AssessmentOut(_Out):
    id: int
    type: str
    total: int
    item_scores: list[int]
    taken_at: str
    risk_alert: bool | None = None


class AssessmentsOut(_Out):
    items: list[AssessmentOut]


class CasePlanOut(_Out):
    id: int
    client_id: int
    version: int
    approach: str
    formulation_text: str
    goals: list[CaseGoal]
    approved_at: str | None = None
    created_at: str
    update_notes: str | None = None
    update_notes_label: str | None = None  # "AI-drafted, approved by <therapist> on <date>"


class CasePlansOut(_Out):
    items: list[CasePlanOut]


class BriefingSuggestion(_Out):
    text: str
    chunk_ids: list[int] = []
    note_quotes: list[str] = []
    label: Literal["SUPPORTED", "INFERRED"] | None = None
    support_note: str | None = None
    already_assigned: dict[str, object] | None = None
    follow_up_note: str | None = None


class RetrievedRef(_Out):
    id: int
    title: str
    similarity: float | None = None


class BriefingBody(_Out):
    client_id: int
    session_starts_at: str
    status: str
    summary: str
    summary_label: str | None = None
    risk_flags: list[str] = []
    scores: dict[str, object] = {}
    plan: dict[str, object] | None = None
    retrieved: list[RetrievedRef] = []
    suggestions: list[BriefingSuggestion] = []


class BriefingItem(_Out):
    id: int
    client_id: int
    status: str
    run_id: str
    briefing: BriefingBody
    created_at: str


class BriefingsOut(_Out):
    items: list[BriefingItem]


class PrepareDayItem(_Out):
    client_id: int
    briefing_id: int | None = None
    pending_action_id: int | None = None
    status: str | None = None
    reused: bool
    error: str | None = None


class PrepareDayOut(_Out):
    items: list[PrepareDayItem]


class OvernightFlag(_Out):
    client_id: int
    findings: list[str]


class OvernightOut(_Out):
    run_id: str
    summary: str
    clients_checked: int
    flagged: list[OvernightFlag]
    drafted: int


class PendingActionOut(_Out):
    id: int
    type: str
    status: str
    practice_id: int
    idempotency_key: str
    decided_by: int | None = None
    decided_at: str | None = None


class ClientView(_Out):
    """Exactly what the client would see if this action is approved."""
    kind: Literal["exercise", "nothing"]
    title: str | None = None
    fields: list[str] = []
    note: str


class PlanSnapshot(_Out):
    approach: str | None = None
    goals: list[str] = []
    formulation: str = ""
    update_notes: str | None = None
    update_notes_label: str | None = None


class PlanDiff(_Out):
    """Case plan before and after approving an apply_plan_update action (server-computed, same code as the apply)."""
    before: PlanSnapshot
    after: PlanSnapshot
    changed: list[str]  # subset of approach, goals, formulation, update_notes
    stale: bool = False  # the plan changed since the draft; approving will be refused


class TherapistActionItem(PendingActionOut):
    payload: dict[str, object]
    client_name: str | None = None
    client_view: ClientView
    diff: PlanDiff | None = None


class TherapistActionsOut(_Out):
    items: list[TherapistActionItem]


class AlertItem(_Out):
    id: int
    client_id: int
    type: str
    priority: str
    payload: dict[str, object]
    acknowledged: bool
    acknowledged_at: str | None = None
    created_at: str


class AlertsOut(_Out):
    items: list[AlertItem]


class AgentRunItem(_Out):
    run_id: str
    step: int
    tool: str
    summary: str
    created_at: str


class AgentRunsOut(_Out):
    items: list[AgentRunItem]


# ---------- owner / admin responses ----------

class VerifyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool = True


class VerifyOut(_Out):
    id: int
    verified: bool
    status: str | None = None


class PracticeItemOut(_Out):
    id: int
    name: str
    slug: str
    status: str
    verified: bool
    page: dict[str, object]


class PracticesOut(_Out):
    items: list[PracticeItemOut]


class OwnerActionItem(PendingActionOut):
    payload: dict[str, object]


class OwnerActionsOut(_Out):
    items: list[OwnerActionItem]


class PracticeDraftOut(_Out):
    id: int
    status: str
    slug: str
    page: dict[str, object]
    run_id: str | None = None
    pending_action: PendingActionOut


class AdminTherapistItem(_Out):
    id: int
    name: str | None = None
    practice_id: int
    practice_name: str
    verified: bool


class AdminTherapistsOut(_Out):
    items: list[AdminTherapistItem]
