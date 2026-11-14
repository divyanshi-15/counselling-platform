"""add alerts.acknowledged_at

Revision ID: 20261115_010
Revises: 20261115_009
Create Date: 2026-11-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261115_010"
down_revision = "20261115_009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE alerts SET acknowledged_at = created_at WHERE acknowledged")


def downgrade() -> None:
    op.drop_column("alerts", "acknowledged_at")
