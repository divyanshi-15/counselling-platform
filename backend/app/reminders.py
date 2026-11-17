"""Gentle reminders, sent by the existing scheduler. Off by default (a client opts in); every send is idempotent via
reminder_log.idempotency_key. Copy is short, kind, English or Hindi, never about streaks or missed days.
Email only; no client text is ever included."""
from __future__ import annotations

import os
import smtplib
from datetime import date, datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Assignment, MoodCheckin, ReminderLog, ReminderPreference, User

COPY = {
    "checkin": {
        "en": ("A quiet moment for you", "Whenever you have a minute today, you can note how you are feeling and how you slept. "
                                         "No pressure at all.\n\nTo stop these reminders, switch them off in My space > Reminders."),
        "hi": ("आपके लिए एक शांत पल", "आज जब भी समय मिले, आप बता सकते हैं कि आप कैसा महसूस कर रहे हैं और नींद कैसी रही। "
                                      "कोई दबाव नहीं है।\n\nये रिमाइंडर बंद करने के लिए: मेरा स्पेस > रिमाइंडर।"),
    },
    "nudge": {
        "en": ("An exercise is waiting for you", "Your therapist shared an exercise with you. Whenever it suits you, "
                                                  "you can open it from My space.\n\nTo stop these reminders, switch them off in My space > Reminders."),
        "hi": ("आपके लिए एक अभ्यास तैयार है", "आपके थेरेपिस्ट ने आपके साथ एक अभ्यास साझा किया है। जब भी आपको ठीक लगे, "
                                              "इसे मेरा स्पेस से खोल सकते हैं।\n\nये रिमाइंडर बंद करने के लिए: मेरा स्पेस > रिमाइंडर।"),
    },
}
NUDGE_AFTER_DAYS = 2
NUDGE_EVERY_DAYS = 3


def send_email(to: str, subject: str, body: str) -> str:
    host, user, password = os.getenv("SMTP_HOST"), os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")
    if not host or not user or not password:
        return "not_configured"
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, os.getenv("SMTP_FROM", user), to
    message.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "1025"))) as connection:
            connection.login(user, password)
            connection.send_message(message)
    except (OSError, smtplib.SMTPException):
        return "failed"
    return "sent"


def _send_once(db: Session, client: User, kind: str, key: str) -> bool:
    """Claim the key first, then send: a second run (or a second process) finds the key and does nothing."""
    log = ReminderLog(client_id=client.id, kind=kind, idempotency_key=key, status="pending")
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    subject, body = COPY[kind]["hi" if client.language == "hi" else "en"]
    log.status = send_email(client.email, subject, body)
    db.commit()
    return log.status == "sent"


def run_reminders(db: Session, today: date | None = None) -> dict[str, int]:
    today = today or datetime.now(timezone.utc).date()
    sent = {"checkin": 0, "nudge": 0}
    prefs = db.scalars(select(ReminderPreference).where(
        (ReminderPreference.daily_checkin.is_(True)) | (ReminderPreference.exercise_nudges.is_(True)))).all()
    for pref in prefs:
        client = db.get(User, pref.client_id)
        if client is None or not client.is_active or client.role != "client":
            continue
        if pref.daily_checkin and db.scalar(select(MoodCheckin.id).where(
                MoodCheckin.client_id == client.id, MoodCheckin.entry_date == today)) is None:
            sent["checkin"] += _send_once(db, client, "checkin", f"checkin:{client.id}:{today.isoformat()}")
        if pref.exercise_nudges:
            waiting = db.scalars(select(Assignment).where(Assignment.client_id == client.id, Assignment.status == "assigned")
                                 .order_by(Assignment.created_at)).first()
            if waiting is not None and (today - waiting.created_at.date()).days >= NUDGE_AFTER_DAYS:
                bucket = today.toordinal() // NUDGE_EVERY_DAYS  # at most one nudge per client every few days
                sent["nudge"] += _send_once(db, client, "nudge", f"nudge:{client.id}:{bucket}")
    return sent
