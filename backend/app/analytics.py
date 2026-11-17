"""Aggregate dashboards. Therapist: own clients only. Practice owner: counts and sums only, no clinical data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, true, union
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from backend.app.auth import require_roles
from backend.app.db import get_db
from backend.app.models import (Alert, Assessment, Assignment, AvailabilitySlot, Booking, CasePlan, Practice,
                                TherapistProfile, User, UserRole)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- therapist -------------------------------------------------------------------------------------------------

class SessionKpi(_Out):
    last_30_days: int
    previous_30_days: int


class MonthPoint(_Out):
    month: str  # YYYY-MM
    average: float


class MeasureSeries(_Out):
    points: list[MonthPoint]
    latest: int | None
    change: int | None  # latest minus earliest reading in the window


class ClientTrend(_Out):
    client_id: int
    name: str | None
    phq9: MeasureSeries
    gad7: MeasureSeries


class TherapistAnalyticsOut(_Out):
    sessions_completed: SessionKpi
    upcoming_sessions_7_days: int
    exercise_completion_rate: float | None
    exercises_assigned: int
    open_alerts: int
    clients: list[ClientTrend]


def _month(ts) -> str:
    return ts.strftime("%Y-%m")


def _month_starts(now: datetime, n: int) -> list[datetime]:
    """First day (UTC midnight) of the last n months, oldest first, including the current month."""
    index = now.year * 12 + now.month - 1
    return [datetime(i // 12, i % 12 + 1, 1, tzinfo=timezone.utc) for i in range(index - n + 1, index + 1)]


def _utc(col):
    return func.timezone("UTC", col)


@router.get("/therapist", response_model=TherapistAnalyticsOut)
def therapist_analytics(
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(UserRole.therapist)),
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    booked_clients = (select(Booking.client_id).join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
                      .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
                      .where(TherapistProfile.user_id == me.id))
    planned_clients = select(CasePlan.client_id).where(CasePlan.therapist_user_id == me.id)
    client_ids = union(booked_clients, planned_clients).subquery()
    in_scope = select(client_ids.c.client_id)

    live = Booking.status != "cancelled"
    d30, d60 = now - timedelta(days=30), now - timedelta(days=60)
    s = AvailabilitySlot.starts_at
    last, prev, upcoming = db.execute(
        select(func.count().filter(live, s >= d30, s < now), func.count().filter(live, s >= d60, s < d30),
               func.count().filter(live, s >= now, s < now + timedelta(days=7)))
        .select_from(Booking).join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
        .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
        .where(TherapistProfile.user_id == me.id)).one()

    assigned, completed = db.execute(
        select(func.count(), func.count().filter(Assignment.status == "completed"))
        .where(Assignment.therapist_user_id == me.id, Assignment.client_id.in_(in_scope))).one()
    open_alerts = db.scalar(select(func.count()).where(Alert.therapist_user_id == me.id, Alert.acknowledged.is_(False)))

    since = _month_starts(now, 6)[0]
    scoped = (Assessment.client_id.in_(in_scope), Assessment.taken_at >= since, Assessment.type.in_(("PHQ9", "GAD7")))
    month = func.date_trunc("month", _utc(Assessment.taken_at)).label("month")
    monthly = db.execute(select(Assessment.client_id, Assessment.type, month, func.avg(Assessment.total))
                         .where(*scoped).group_by(Assessment.client_id, Assessment.type, month).order_by(month)).all()
    edge = {}
    for direction, name in ((Assessment.taken_at.desc(), "latest"), (Assessment.taken_at.asc(), "first")):
        edge[name] = {(c, t): v for c, t, v in db.execute(
            select(Assessment.client_id, Assessment.type, Assessment.total)
            .where(*scoped).ext(distinct_on(Assessment.client_id, Assessment.type))
            .order_by(Assessment.client_id, Assessment.type, direction)).all()}
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_({c for c, *_ in monthly}))).all())

    points: dict[tuple[int, str], list[dict]] = {}
    for client_id, kind, m, avg in monthly:
        points.setdefault((client_id, kind), []).append({"month": _month(m), "average": round(float(avg), 1)})

    def series(client_id: int, kind: str) -> dict[str, object]:
        latest, first = edge["latest"].get((client_id, kind)), edge["first"].get((client_id, kind))
        return {"points": points.get((client_id, kind), []), "latest": latest,
                "change": None if latest is None else latest - first}

    ids = sorted({c for c, *_ in monthly}, key=lambda c: (names.get(c) or "", c))
    return {"sessions_completed": {"last_30_days": last, "previous_30_days": prev},
            "upcoming_sessions_7_days": upcoming,
            "exercise_completion_rate": round(completed / assigned, 3) if assigned else None,
            "exercises_assigned": assigned, "open_alerts": open_alerts,
            "clients": [{"client_id": c, "name": names.get(c), "phq9": series(c, "PHQ9"), "gad7": series(c, "GAD7")}
                        for c in ids]}


# ---- practice owner: counts and sums only ----------------------------------------------------------------------

class WeekCount(_Out):
    week_start: str  # YYYY-MM-DD
    bookings: int


class TherapistUtilisation(_Out):
    therapist: str | None
    booked_slots: int
    available_slots: int
    utilisation: float | None


class UtilisationOut(_Out):
    booked_slots: int
    available_slots: int
    utilisation: float | None
    by_therapist: list[TherapistUtilisation]


class MonthRevenue(_Out):
    month: str  # YYYY-MM
    sessions: int
    revenue_inr: int


class SpecialisationCount(_Out):
    specialisation: str
    bookings: int


class PracticeAnalyticsOut(_Out):
    bookings_per_week: list[WeekCount]
    utilisation_next_14_days: UtilisationOut
    revenue_per_month: list[MonthRevenue]
    top_specialisations: list[SpecialisationCount]


def _ratio(booked: int, available: int) -> float | None:
    return round(booked / available, 3) if available else None


@router.get("/practice", response_model=PracticeAnalyticsOut)
def practice_analytics(
    db: Session = Depends(get_db),
    me: User = Depends(require_roles(UserRole.practice_owner)),
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    live = Booking.status != "cancelled"
    start_utc = _utc(AvailabilitySlot.starts_at)

    def bookings():
        return (select().select_from(Booking)
                .join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
                .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
                .join(Practice, Practice.id == TherapistProfile.practice_id)
                .where(Practice.owner_id == me.id, live))

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_week = today - timedelta(days=today.weekday())
    week0 = this_week - timedelta(weeks=11)
    week = func.date_trunc("week", start_utc).label("week")
    by_week = dict(db.execute(bookings().add_columns(week, func.count()).where(start_utc >= week0.replace(tzinfo=None),
                                                                              start_utc < (this_week + timedelta(weeks=1)).replace(tzinfo=None))
                              .group_by(week)).all())
    weeks = [{"week_start": (week0 + timedelta(weeks=i)).date().isoformat(),
              "bookings": by_week.get((week0 + timedelta(weeks=i)).replace(tzinfo=None), 0)} for i in range(12)]

    months = _month_starts(now, 6)
    month = func.date_trunc("month", start_utc).label("month")
    revenue = {m: (n, int(r)) for m, n, r in db.execute(
        bookings().add_columns(month, func.count(), func.coalesce(func.sum(TherapistProfile.fee), 0))
        .where(start_utc >= months[0].replace(tzinfo=None)).group_by(month)).all()}
    revenue_rows = [{"month": _month(m), "sessions": revenue.get(m.replace(tzinfo=None), (0, 0))[0],
                     "revenue_inr": revenue.get(m.replace(tzinfo=None), (0, 0))[1]} for m in months]

    has_booking = select(Booking.id).where(Booking.availability_slot_id == AvailabilitySlot.id, live).exists()
    util = db.execute(
        select(User.name, func.count().filter(has_booking), func.count())
        .select_from(AvailabilitySlot).join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
        .join(Practice, Practice.id == TherapistProfile.practice_id).join(User, User.id == TherapistProfile.user_id)
        .where(Practice.owner_id == me.id, AvailabilitySlot.starts_at >= now,
               AvailabilitySlot.starts_at < now + timedelta(days=14))
        .group_by(TherapistProfile.id, User.name).order_by(User.name)).all()
    total_booked, total_slots = sum(r[1] for r in util), sum(r[2] for r in util)

    spec = func.json_array_elements_text(TherapistProfile.specialisations).table_valued("value").lateral()
    top = db.execute(
        select(spec.c.value, func.count(Booking.id))
        .select_from(Booking).join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
        .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
        .join(Practice, Practice.id == TherapistProfile.practice_id).join(spec, true())
        .where(Practice.owner_id == me.id, live, start_utc >= months[0].replace(tzinfo=None))
        .group_by(spec.c.value).order_by(func.count(Booking.id).desc(), spec.c.value).limit(5)).all()

    return {"bookings_per_week": weeks,
            "utilisation_next_14_days": {
                "booked_slots": total_booked, "available_slots": total_slots, "utilisation": _ratio(total_booked, total_slots),
                "by_therapist": [{"therapist": n, "booked_slots": b, "available_slots": a, "utilisation": _ratio(b, a)}
                                 for n, b, a in util]},
            "revenue_per_month": revenue_rows,
            "top_specialisations": [{"specialisation": s, "bookings": n} for s, n in top]}
