"""add case_plans.update_notes (approved AI draft, kept apart from the therapist's formulation)

Revision ID: 20261115_011
Revises: 20261115_010
Create Date: 2026-11-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261115_011"
down_revision = "20261115_010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("case_plans", sa.Column("update_notes", sa.Text(), nullable=True))
    op.add_column("case_plans", sa.Column("update_notes_approved_by", sa.Integer(), nullable=True))
    op.add_column("case_plans", sa.Column("update_notes_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_case_plans_update_notes_approved_by", "case_plans", "users",
                          ["update_notes_approved_by"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_case_plans_update_notes_approved_by", "case_plans", type_="foreignkey")
    op.drop_column("case_plans", "update_notes_approved_at")
    op.drop_column("case_plans", "update_notes_approved_by")
    op.drop_column("case_plans", "update_notes")
