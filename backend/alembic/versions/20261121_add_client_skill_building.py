"""client skill-building: mood check-ins, journal, journeys, reminders

Revision ID: 20261121_017
Revises: 20261120_016
Create Date: 2026-11-21 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261121_017"
down_revision = "20261120_016"
branch_labels = None
depends_on = None

_ts = lambda name: sa.Column(name, sa.DateTime(timezone=True), nullable=False)  # noqa: E731
_user = lambda name, nullable=False: sa.Column(name, sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=nullable, index=True)  # noqa: E731


def upgrade() -> None:
    op.create_table("mood_checkins",
                    sa.Column("id", sa.Integer(), primary_key=True), _user("client_id"),
                    sa.Column("entry_date", sa.Date(), nullable=False), sa.Column("mood", sa.Integer(), nullable=False),
                    sa.Column("sleep_hours", sa.Float(), nullable=False), sa.Column("note", sa.String(500)),
                    _ts("created_at"), _ts("updated_at"),
                    sa.UniqueConstraint("client_id", "entry_date", name="uq_mood_client_day"))
    op.create_table("journal_entries",
                    sa.Column("id", sa.Integer(), primary_key=True), _user("client_id"),
                    sa.Column("text", sa.String(2000), nullable=False),
                    sa.Column("shared", sa.Boolean(), nullable=False, server_default="false"),
                    sa.Column("idempotency_key", sa.String(100)), _ts("created_at"),
                    sa.UniqueConstraint("client_id", "idempotency_key", name="uq_journal_client_key"))
    op.create_table("journeys",
                    sa.Column("id", sa.Integer(), primary_key=True), _user("created_by", nullable=True),
                    sa.Column("slug", sa.String(64), unique=True), sa.Column("title_en", sa.String(200), nullable=False),
                    sa.Column("title_hi", sa.String(200)), _ts("created_at"))
    op.create_table("journey_steps",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("journey_id", sa.Integer(), sa.ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True),
                    sa.Column("week", sa.Integer(), nullable=False), sa.Column("position", sa.Integer(), nullable=False),
                    sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", ondelete="RESTRICT"), nullable=False),
                    sa.Column("text_en", sa.String(400), nullable=False), sa.Column("text_hi", sa.String(400)))
    op.create_table("journey_assignments",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("journey_id", sa.Integer(), sa.ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False, index=True),
                    _user("client_id"), _user("therapist_user_id"),
                    sa.Column("started_on", sa.Date(), nullable=False),
                    sa.Column("idempotency_key", sa.String(255), nullable=False), _ts("created_at"),
                    sa.UniqueConstraint("client_id", "idempotency_key", name="uq_journey_assignment_key"))
    op.create_table("journey_step_progress",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("journey_assignments.id", ondelete="CASCADE"), nullable=False, index=True),
                    sa.Column("step_id", sa.Integer(), sa.ForeignKey("journey_steps.id", ondelete="CASCADE"), nullable=False),
                    _ts("completed_at"),
                    sa.UniqueConstraint("assignment_id", "step_id", name="uq_journey_progress"))
    op.create_table("reminder_preferences",
                    sa.Column("client_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("daily_checkin", sa.Boolean(), nullable=False, server_default="false"),
                    sa.Column("exercise_nudges", sa.Boolean(), nullable=False, server_default="false"),
                    _ts("updated_at"))
    op.create_table("reminder_log",
                    sa.Column("id", sa.Integer(), primary_key=True), _user("client_id"),
                    sa.Column("kind", sa.String(24), nullable=False),
                    sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
                    sa.Column("status", sa.String(16), nullable=False), _ts("created_at"))


    for table in ("mood_checkins", "journal_entries", "journeys", "journey_steps", "journey_assignments",
                  "journey_step_progress", "reminder_log"):
        op.create_index(f"ix_{table}_id", table, ["id"])


def downgrade() -> None:
    for table in ("reminder_log", "reminder_preferences", "journey_step_progress", "journey_assignments",
                  "journey_steps", "journeys", "journal_entries", "mood_checkins"):
        op.drop_table(table)
