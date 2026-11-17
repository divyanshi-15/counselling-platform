"""Deterministic clinical helpers shared by endpoints and agents. No LLM calls here."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Alert, MoodCheckin
from backend.app.safety import free_text_values, risk_scan

ASSESSMENT_ITEMS = {"PHQ9": 9, "GAD7": 7}


def scan_client_text(value: object) -> dict | None:
    """Run the safety layer over every free-text string in value. Returns the first hit, else None."""
    for text in free_text_values(value):
        result = risk_scan(text)
        if result["flagged"]:
            return result | {"text": text}
    return None


def raise_risk_alert(db: Session, *, therapist_user_id: int, client_id: int, source: str,
                     source_id: int | None, match: str | None, text: str | None = None) -> Alert:
    # payload["text"] (the triggering words) is shown only to the assigned therapist via /therapists/me/alerts;
    # it must never be logged or put into emails/notifications.
    payload = {"source": source, "source_id": source_id, "match": match}
    if text:
        payload["text"] = text
    alert = Alert(therapist_user_id=therapist_user_id, client_id=client_id, type="risk", priority="high", payload=payload)
    db.add(alert)
    return alert


def assessment_total(kind: str, item_scores: list[int]) -> int:
    expected = ASSESSMENT_ITEMS.get(kind)
    if expected is None:
        raise ValueError("type must be PHQ9 or GAD7")
    if len(item_scores) != expected or any(not isinstance(s, int) or s < 0 or s > 3 for s in item_scores):
        raise ValueError(f"{kind} needs {expected} item scores, each 0-3")
    return sum(item_scores)


def phq9_item9_positive(kind: str, item_scores: list[int]) -> bool:
    return kind == "PHQ9" and len(item_scores) == 9 and item_scores[8] > 0


def mood_trend(db: Session, client_id: int, days: int = 14, today: date | None = None) -> dict:
    """Plain numbers only (mood 1-5, sleep hours): no interpretation. The free-text note is never included."""
    end = today or date.today()
    rows = db.scalars(select(MoodCheckin).where(MoodCheckin.client_id == client_id,
                                                MoodCheckin.entry_date > end - timedelta(days=days),
                                                MoodCheckin.entry_date <= end + timedelta(days=1))
                      .order_by(MoodCheckin.entry_date.asc())).all()
    n = len(rows)
    return {"days": days, "count": n,
            "avg_mood": round(sum(r.mood for r in rows) / n, 1) if n else None,
            "avg_sleep": round(sum(r.sleep_hours for r in rows) / n, 1) if n else None,
            "entries": [{"date": r.entry_date.isoformat(), "mood": r.mood, "sleep_hours": r.sleep_hours} for r in rows]}
