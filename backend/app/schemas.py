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
