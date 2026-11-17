"""Client skill-building: mood check-in, private journal, insights, reminder preferences. No model calls in this module.
Every client free-text field goes through the safety check first; a hit stops the request with the fixed crisis message."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import require_roles, require_therapist_of_client
from backend.app.braindump import client_therapist
from backend.app.clinical import mood_trend, raise_risk_alert, scan_client_text
from backend.app.db import get_db
from backend.app.exercises import with_notice
from backend.app.models import Alert, Assignment, Checkin, JournalEntry, MoodCheckin, ReminderPreference, User, UserRole
from backend.app.ratelimit import client_rate_limit
from backend.app.safety import crisis_message

router = APIRouter()
client_only = require_roles(UserRole.client)

MAX_NOTE = 500
MAX_JOURNAL = 2000


class _Notice(BaseModel):
    notice: str
    crisis_line: str


class MoodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mood: int = Field(ge=1, le=5)
    sleep_hours: float = Field(ge=0, le=24)
    note: str | None = Field(default=None, max_length=MAX_NOTE)
    entry_date: date | None = None  # the client's local date; defaults to today (UTC)

    @field_validator("note")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v else None


class MoodEntry(BaseModel):
    entry_date: str
    mood: int
    sleep_hours: float
    note: str | None = None


class MoodOut(_Notice):
    status: str  # saved | crisis
    message: str | None = None
    entry: MoodEntry | None = None


class MoodListOut(_Notice):
    items: list[MoodEntry]


class JournalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_JOURNAL)
    shared: bool = False

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Write something first")
        return v.strip()


class JournalShareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shared: bool


class JournalItem(BaseModel):
    id: int
    text: str
    shared: bool
    created_at: str


class JournalOut(_Notice):
    status: str  # saved | crisis
    message: str | None = None
    entry: JournalItem | None = None


class JournalListOut(_Notice):
    items: list[JournalItem]


class SharedJournalItem(BaseModel):
    id: int
    text: str
    created_at: str


class SharedJournalOut(BaseModel):
    items: list[SharedJournalItem]


class TrendEntry(BaseModel):
    date: str
    mood: int
    sleep_hours: float


class MoodTrendOut(BaseModel):
    days: int
    count: int
    avg_mood: float | None = None
    avg_sleep: float | None = None
    entries: list[TrendEntry]


class InsightDay(BaseModel):
    date: str
    mood: int | None = None
    sleep_hours: float | None = None
    exercises_completed: int = 0


class InsightsOut(_Notice):
    days: int
    series: list[InsightDay]
    checkins: int
    avg_mood: float | None = None
    avg_sleep: float | None = None
    exercises_completed: int
    exercises_assigned: int


class RemindersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_checkin: bool
    exercise_nudges: bool


class RemindersOut(_Notice):
    daily_checkin: bool
    exercise_nudges: bool


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _mood_entry(r: MoodCheckin) -> dict[str, Any]:
    return {"entry_date": r.entry_date.isoformat(), "mood": r.mood, "sleep_hours": r.sleep_hours, "note": r.note}


def _journal_item(r: JournalEntry) -> dict[str, Any]:
    return {"id": r.id, "text": r.text, "shared": r.shared, "created_at": r.created_at.isoformat()}


def stop_for_crisis(db: Session, user: User, hit: dict, *, source: str, dedupe: str) -> dict[str, Any]:
    """Safety stop: fixed crisis text and a high-priority alert to the client's therapist. No model, nothing saved.
    The dedupe key makes a repeated identical submission raise one alert, not several."""
    owner = client_therapist(db, user.id)
    key = f"risk:{source}:{user.id}:{dedupe}"
    if owner is not None and db.scalar(select(Alert.id).where(Alert.dedupe_key == key)) is None:
        alert = raise_risk_alert(db, therapist_user_id=owner[0], client_id=user.id, source=source, source_id=None,
                                 match=hit["match"], text=hit["text"])
        alert.dedupe_key = key
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return with_notice({"status": "crisis", "message": crisis_message(user.language)})


# ---------- mood check-in ----------

@router.put("/client/mood", dependencies=[Depends(client_rate_limit)], response_model=MoodOut)
def save_mood(payload: MoodIn, db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    day = payload.entry_date or _utc_today()
    if abs((day - _utc_today()).days) > 1:
        raise HTTPException(status_code=422, detail="Check-ins are for today only")
    if payload.note:
        hit = scan_client_text(payload.note)  # before anything is stored
        if hit:
            digest = hashlib.sha256(payload.note.encode()).hexdigest()[:16]
            return stop_for_crisis(db, user, hit, source="mood_checkin", dedupe=f"{day}:{digest}")
    now = datetime.now(timezone.utc)
    row = db.scalar(select(MoodCheckin).where(MoodCheckin.client_id == user.id, MoodCheckin.entry_date == day))
    if row is None:
        row = MoodCheckin(client_id=user.id, entry_date=day, mood=payload.mood, sleep_hours=payload.sleep_hours,
                          note=payload.note, created_at=now, updated_at=now)
        db.add(row)
    else:
        row.mood, row.sleep_hours, row.note, row.updated_at = payload.mood, payload.sleep_hours, payload.note, now
    try:
        db.commit()
    except IntegrityError:  # two first-of-the-day requests raced: the other one won, so update its row
        db.rollback()
        row = db.scalar(select(MoodCheckin).where(MoodCheckin.client_id == user.id, MoodCheckin.entry_date == day))
        row.mood, row.sleep_hours, row.note, row.updated_at = payload.mood, payload.sleep_hours, payload.note, now
        db.commit()
    return with_notice({"status": "saved", "entry": _mood_entry(row)})


@router.get("/client/mood", dependencies=[Depends(client_rate_limit)], response_model=MoodListOut)
def list_mood(days: int = Query(default=14, ge=1, le=90), db: Session = Depends(get_db),
              user: User = Depends(client_only)) -> dict[str, Any]:
    rows = db.scalars(select(MoodCheckin).where(MoodCheckin.client_id == user.id,
                                                MoodCheckin.entry_date > _utc_today() - timedelta(days=days))
                      .order_by(MoodCheckin.entry_date.desc())).all()
    return with_notice({"items": [_mood_entry(r) for r in rows]})


@router.get("/clients/{client_id}/mood-trend", response_model=MoodTrendOut)
def client_mood_trend(client_id: int, db: Session = Depends(get_db),
                      _: User = Depends(require_therapist_of_client)) -> dict[str, Any]:
    return mood_trend(db, client_id, 14)


# ---------- journal ----------

@router.post("/client/journal", dependencies=[Depends(client_rate_limit)], response_model=JournalOut)
def add_journal_entry(payload: JournalIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                      db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    if not idempotency_key or len(idempotency_key) > 100:
        raise HTTPException(status_code=422, detail="An Idempotency-Key header is required")
    prior = db.scalar(select(JournalEntry).where(JournalEntry.client_id == user.id,
                                                 JournalEntry.idempotency_key == idempotency_key))
    if prior is not None:
        return with_notice({"status": "saved", "entry": _journal_item(prior)})
    hit = scan_client_text(payload.text)  # before anything is stored
    if hit:
        digest = hashlib.sha256(payload.text.encode()).hexdigest()[:16]
        return stop_for_crisis(db, user, hit, source="journal", dedupe=f"{_utc_today()}:{digest}")
    row = JournalEntry(client_id=user.id, text=payload.text, shared=payload.shared, idempotency_key=idempotency_key)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # concurrent replay of the same key
        db.rollback()
        row = db.scalar(select(JournalEntry).where(JournalEntry.client_id == user.id,
                                                   JournalEntry.idempotency_key == idempotency_key))
    return with_notice({"status": "saved", "entry": _journal_item(row)})


@router.get("/client/journal", dependencies=[Depends(client_rate_limit)], response_model=JournalListOut)
def list_journal(db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    rows = db.scalars(select(JournalEntry).where(JournalEntry.client_id == user.id)
                      .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()).limit(200)).all()
    return with_notice({"items": [_journal_item(r) for r in rows]})


@router.patch("/client/journal/{entry_id}", dependencies=[Depends(client_rate_limit)], response_model=JournalItem)
def set_journal_sharing(entry_id: int, payload: JournalShareIn, db: Session = Depends(get_db),
                        user: User = Depends(client_only)) -> dict[str, Any]:
    row = db.get(JournalEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if row.client_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    row.shared = payload.shared
    db.commit()
    return _journal_item(row)


@router.get("/clients/{client_id}/journal", response_model=SharedJournalOut)
def shared_journal(client_id: int, db: Session = Depends(get_db),
                   _: User = Depends(require_therapist_of_client)) -> dict[str, Any]:
    """Only entries the client chose to share. Private entries are never returned."""
    rows = db.scalars(select(JournalEntry).where(JournalEntry.client_id == client_id, JournalEntry.shared.is_(True))
                      .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()).limit(50)).all()
    return {"items": [{"id": r.id, "text": r.text, "created_at": r.created_at.isoformat()} for r in rows]}


# ---------- insights ----------

@router.get("/client/insights", dependencies=[Depends(client_rate_limit)], response_model=InsightsOut)
def insights(db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    """Plain numbers over the last 30 days. No interpretation."""
    days = 30
    today = _utc_today()
    start = today - timedelta(days=days - 1)
    moods = {r.entry_date: r for r in db.scalars(select(MoodCheckin).where(
        MoodCheckin.client_id == user.id, MoodCheckin.entry_date >= start))}
    done = dict(db.execute(
        select(func.date(Checkin.completed_at), func.count()).join(Assignment, Assignment.id == Checkin.assignment_id)
        .where(Assignment.client_id == user.id, Checkin.flagged.is_(False), func.date(Checkin.completed_at) >= start)
        .group_by(func.date(Checkin.completed_at))).all())
    series = []
    for i in range(days):
        d = start + timedelta(days=i)
        m = moods.get(d)
        series.append({"date": d.isoformat(), "mood": m.mood if m else None,
                       "sleep_hours": m.sleep_hours if m else None, "exercises_completed": int(done.get(d, 0))})
    n = len(moods)
    assigned = db.scalar(select(func.count()).select_from(Assignment).where(
        Assignment.client_id == user.id, func.date(Assignment.created_at) >= start)) or 0
    return with_notice({"days": days, "series": series, "checkins": n,
                        "avg_mood": round(sum(m.mood for m in moods.values()) / n, 1) if n else None,
                        "avg_sleep": round(sum(m.sleep_hours for m in moods.values()) / n, 1) if n else None,
                        "exercises_completed": sum(done.values()), "exercises_assigned": assigned})


# ---------- reminder preferences (off by default) ----------

@router.get("/client/reminders", dependencies=[Depends(client_rate_limit)], response_model=RemindersOut)
def get_reminders(db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    pref = db.get(ReminderPreference, user.id)
    return with_notice({"daily_checkin": bool(pref and pref.daily_checkin), "exercise_nudges": bool(pref and pref.exercise_nudges)})


@router.put("/client/reminders", dependencies=[Depends(client_rate_limit)], response_model=RemindersOut)
def set_reminders(payload: RemindersIn, db: Session = Depends(get_db), user: User = Depends(client_only)) -> dict[str, Any]:
    pref = db.get(ReminderPreference, user.id)
    if pref is None:
        pref = ReminderPreference(client_id=user.id)
        db.add(pref)
    pref.daily_checkin, pref.exercise_nudges = payload.daily_checkin, payload.exercise_nudges
    pref.updated_at = datetime.now(timezone.utc)
    db.commit()
    return with_notice({"daily_checkin": pref.daily_checkin, "exercise_nudges": pref.exercise_nudges})
