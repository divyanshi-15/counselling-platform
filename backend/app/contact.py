"""Public contact form. Every message is saved first; email delivery is best effort and never shown to the visitor.
Safety runs before anything else, with no model call."""
from __future__ import annotations

import logging
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import require_roles
from backend.app.clinical import scan_client_text
from backend.app.db import get_db
from backend.app.models import ContactMessage, UserRole
from backend.app.ratelimit import rate_limit
from backend.app.safety import crisis_message

log = logging.getLogger(__name__)
router = APIRouter(tags=["contact"])
contact_form_limit = rate_limit("contact_form", "RATE_LIMIT_CONTACT_PER_HOUR", 5, window_seconds=3600)
admin_only = require_roles(UserRole.admin)

RECEIVED = "Thank you. Your message has been received and we will reply by email."
_CONTROL = re.compile(r"[\x00-\x1f\x7f  ]+")
_EMAIL = re.compile(r"^[^@\s<>,;\"]+@[^@\s<>,;\"]+\.[^@\s<>,;\"]+$")


class ContactIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    message: str = Field(min_length=1, max_length=1500)
    website: str = Field(default="", max_length=500)  # honeypot: hidden from people, filled in by bots
    language: Literal["en", "hi"] = "en"


class ContactOut(BaseModel):
    status: Literal["received", "crisis"]
    message: str


class ContactMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    message: str
    high_priority: bool
    email_status: str
    created_at: datetime


def _clean(value: str) -> str:
    """Remove CR/LF and other control characters so a value can never add or break a mail header."""
    return _CONTROL.sub(" ", value).strip()


def _transport() -> smtplib.SMTP:
    host, port = os.getenv("SMTP_HOST", ""), int(os.getenv("SMTP_PORT") or "587")
    mode = (os.getenv("SMTP_SECURE") or {465: "ssl", 587: "starttls"}.get(port, "none")).lower()
    if mode == "ssl":
        return smtplib.SMTP_SSL(host, port, timeout=10)
    connection = smtplib.SMTP(host, port, timeout=10)
    if mode == "starttls":
        connection.starttls()
    return connection


def send_contact_email(row: ContactMessage) -> str:
    """Returns sent | failed | not_configured. The password is never logged."""
    host, to = os.getenv("SMTP_HOST"), os.getenv("CONTACT_TO")
    if not host or not to:
        return "not_configured"
    user, password = os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")
    message = EmailMessage()
    message["Subject"] = f"[Saarthi contact] {row.name}"[:150]
    message["From"] = os.getenv("SMTP_FROM") or user or to
    message["To"] = to
    message["Reply-To"] = row.email
    message.set_content(f"Name: {row.name}\nEmail: {row.email}\n\n{row.message}\n")
    try:
        with _transport() as connection:
            if user and password:
                connection.login(user, password)
            connection.send_message(message)
    except Exception as exc:  # delivery must never break the visitor's request
        log.warning("contact email failed for message %s: %s", row.id, type(exc).__name__)
        return "failed"
    return "sent"


@router.post("/contact", response_model=ContactOut, dependencies=[Depends(contact_form_limit)])
def submit_contact(payload: ContactIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
                   db: Session = Depends(get_db)):
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="An Idempotency-Key header is required")
    if payload.website:
        return {"status": "received", "message": RECEIVED}  # honeypot: look successful, save nothing
    existing = db.query(ContactMessage).filter(ContactMessage.idempotency_key == idempotency_key).first()
    if existing is not None:  # replay: same answer, no second row or email
        return ({"status": "crisis", "message": crisis_message(payload.language)} if existing.high_priority
                else {"status": "received", "message": RECEIVED})
    name, email = _clean(payload.name), _clean(payload.email)
    if not name or not _EMAIL.match(email):
        raise HTTPException(status_code=422, detail="Enter your name and a valid email address")
    crisis = scan_client_text({"name": name, "message": payload.message}) is not None
    row = ContactMessage(name=name, email=email, message=payload.message, idempotency_key=idempotency_key,
                         high_priority=crisis, email_status="skipped" if crisis else "pending")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # a parallel request with the same key won the race
        db.rollback()
        return {"status": "crisis" if crisis else "received", "message": crisis_message(payload.language) if crisis else RECEIVED}
    if crisis:  # fixed text only; no model, no email
        return {"status": "crisis", "message": crisis_message(payload.language)}
    row.email_status = send_contact_email(row)
    db.commit()
    return {"status": "received", "message": RECEIVED}


@router.get("/admin/contact-messages", response_model=list[ContactMessageOut])
def list_contact_messages(db: Session = Depends(get_db), _=Depends(admin_only)):
    return (db.query(ContactMessage).order_by(ContactMessage.high_priority.desc(), ContactMessage.id.desc()).limit(200).all())
