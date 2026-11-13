"""add therapist profiles, availability, bookings, and intake tables

Revision ID: 20261114_003
Revises: 20261114_002
Create Date: 2026-11-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261114_003"
down_revision = "20261114_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "therapist_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("practice_id", sa.Integer(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("approaches", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("languages", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("fee", sa.Integer(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["practice_id"], ["practices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_therapist_profiles_id"), "therapist_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_therapist_profiles_practice_id"), "therapist_profiles", ["practice_id"], unique=False)

    op.create_table(
        "availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("therapist_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["therapist_id"], ["therapist_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("therapist_id", "starts_at", "ends_at", name="uq_availability_therapist_time"),
    )
    op.create_index(op.f("ix_availability_slots_id"), "availability_slots", ["id"], unique=False)
    op.create_index(op.f("ix_availability_slots_therapist_id"), "availability_slots", ["therapist_id"], unique=False)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("availability_slot_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["availability_slot_id"], ["availability_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("availability_slot_id"),
    )
    op.create_index(op.f("ix_bookings_id"), "bookings", ["id"], unique=False)
    op.create_index(op.f("ix_bookings_client_id"), "bookings", ["client_id"], unique=False)

    op.create_table(
        "intake_forms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("therapist_id", sa.Integer(), nullable=False),
        sa.Column("fields_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["therapist_id"], ["therapist_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("therapist_id"),
    )
    op.create_index(op.f("ix_intake_forms_id"), "intake_forms", ["id"], unique=False)

    op.create_table(
        "intake_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("answers_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )
    op.create_index(op.f("ix_intake_responses_id"), "intake_responses", ["id"], unique=False)
    op.create_index(op.f("ix_intake_responses_client_id"), "intake_responses", ["client_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_intake_responses_client_id"), table_name="intake_responses")
    op.drop_index(op.f("ix_intake_responses_id"), table_name="intake_responses")
    op.drop_table("intake_responses")
    op.drop_index(op.f("ix_intake_forms_id"), table_name="intake_forms")
    op.drop_table("intake_forms")
    op.drop_index(op.f("ix_bookings_client_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_id"), table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(op.f("ix_availability_slots_therapist_id"), table_name="availability_slots")
    op.drop_index(op.f("ix_availability_slots_id"), table_name="availability_slots")
    op.drop_table("availability_slots")
    op.drop_index(op.f("ix_therapist_profiles_practice_id"), table_name="therapist_profiles")
    op.drop_index(op.f("ix_therapist_profiles_id"), table_name="therapist_profiles")
    op.drop_table("therapist_profiles")
