"""add sessions, case plans, assessments, alerts, copilot briefings; scope actions/runs to an owner

Revision ID: 20261114_005
Revises: 20261114_004
Create Date: 2026-11-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261114_005"
down_revision = "20261114_004"
branch_labels = None
depends_on = None


def _user_fk(col: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([col], ["users.id"], ondelete="CASCADE")


def upgrade() -> None:
    op.add_column("pending_actions", sa.Column("assignee_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "pending_actions", "users", ["assignee_user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_pending_actions_assignee_user_id", "pending_actions", ["assignee_user_id"])
    op.add_column("agent_runs", sa.Column("agent", sa.String(length=32), nullable=False, server_default="launch"))
    op.add_column("agent_runs", sa.Column("actor_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "agent_runs", "users", ["actor_user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_agent_runs_actor_user_id", "agent_runs", ["actor_user_id"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("note_source", sa.String(length=16), nullable=False),
        sa.Column("raw_notes", sa.Text(), nullable=False),
        sa.Column("structured_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("structured_status", sa.String(length=16), nullable=False),
        sa.Column("risk_flag", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        _user_fk("client_id"), _user_fk("therapist_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )
    for col in ("id", "client_id", "therapist_user_id"):
        op.create_index(f"ix_sessions_{col}", "sessions", [col])

    op.create_table(
        "case_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("approach", sa.String(length=32), nullable=False),
        sa.Column("formulation_text", sa.Text(), nullable=False),
        sa.Column("goals_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("client_id"), _user_fk("therapist_user_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "therapist_user_id", "version", name="uq_case_plan_version"),
    )
    for col in ("id", "client_id", "therapist_user_id"):
        op.create_index(f"ix_case_plans_{col}", "case_plans", [col])

    op.create_table(
        "assessments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=8), nullable=False),
        sa.Column("item_scores", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("client_id"), _user_fk("recorded_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("id", "client_id"):
        op.create_index(f"ix_assessments_{col}", "assessments", [col])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("therapist_user_id"), _user_fk("client_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("id", "therapist_user_id", "client_id"):
        op.create_index(f"ix_alerts_{col}", "alerts", [col])

    op.create_table(
        "copilot_briefings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("briefing_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("therapist_user_id"), _user_fk("client_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("id", "therapist_user_id", "client_id"):
        op.create_index(f"ix_copilot_briefings_{col}", "copilot_briefings", [col])


def downgrade() -> None:
    for table in ("copilot_briefings", "alerts", "assessments", "case_plans", "sessions"):
        op.drop_table(table)
    op.drop_index("ix_agent_runs_actor_user_id", "agent_runs")
    op.drop_column("agent_runs", "actor_user_id")
    op.drop_column("agent_runs", "agent")
    op.drop_index("ix_pending_actions_assignee_user_id", "pending_actions")
    op.drop_column("pending_actions", "assignee_user_id")
