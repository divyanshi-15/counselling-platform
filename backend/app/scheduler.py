"""Nightly monitoring job. One uvicorn worker (see Dockerfile) means exactly one scheduler; a Postgres
advisory lock additionally guards against a second process, and the job is idempotent per (client, date, type)."""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from backend.app.agents.monitor import run_all_therapists
from backend.app.db import SessionLocal
from backend.app.reminders import run_reminders

log = logging.getLogger(__name__)
LOCK_ID = 7305001
REMINDER_LOCK_ID = 7305002


def nightly_job() -> None:
    with SessionLocal() as db:
        if not db.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}):
            return
        try:
            runs = run_all_therapists(db)
            log.info("overnight check: %s", [r["summary"] for r in runs])
        finally:
            db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            db.commit()


def reminder_job() -> None:
    with SessionLocal() as db:
        if not db.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": REMINDER_LOCK_ID}):
            return
        try:
            log.info("reminders sent: %s", run_reminders(db))
        finally:
            db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": REMINDER_LOCK_ID})
            db.commit()


def start_scheduler() -> BackgroundScheduler | None:
    if os.getenv("APP_ENV") == "test" or os.getenv("SCHEDULER_ENABLED", "1") == "0":
        return None
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(nightly_job, CronTrigger(hour=int(os.getenv("OVERNIGHT_HOUR_UTC", "21"))),
                      id="overnight_check", max_instances=1, coalesce=True, replace_existing=True)
    scheduler.add_job(reminder_job, CronTrigger(hour=int(os.getenv("REMINDER_HOUR_UTC", "4"))),
                      id="gentle_reminders", max_instances=1, coalesce=True, replace_existing=True)
    scheduler.start()
    return scheduler
