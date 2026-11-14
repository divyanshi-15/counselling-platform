"""add checkins.flagged

Revision ID: 20261114_007
Revises: 20261114_006
Create Date: 2026-11-14 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261114_007"
down_revision = "20261114_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checkins", sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("checkins", "flagged")
