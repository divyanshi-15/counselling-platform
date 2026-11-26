"""audit_log note for admin review decisions

Revision ID: 20261120_016
Revises: 20261119_015
Create Date: 2026-11-20 09:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20261120_016"
down_revision = "20261119_015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_log", "note")
