from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "client"
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
