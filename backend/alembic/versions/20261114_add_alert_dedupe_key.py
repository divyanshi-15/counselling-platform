"""add alerts.dedupe_key (monitoring idempotency per client, date, type)

Revision ID: 20261114_008
Revises: 20261114_007
Create Date: 2026-11-14 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261114_008"
down_revision = "20261114_007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("dedupe_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_alerts_dedupe_key", "alerts", ["dedupe_key"])


def downgrade() -> None:
    op.drop_constraint("uq_alerts_dedupe_key", "alerts", type_="unique")
    op.drop_column("alerts", "dedupe_key")
