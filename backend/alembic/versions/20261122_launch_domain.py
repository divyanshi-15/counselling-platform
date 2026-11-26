"""idea-to-launch: practice custom domain, agent trace columns

Revision ID: 20261122_018
Revises: 20261121_017
Create Date: 2026-11-22 09:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20261122_018"
down_revision = "20261121_017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("practices", sa.Column("custom_domain", sa.String(253), nullable=True))
    op.add_column("practices", sa.Column("domain_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_practices_custom_domain", "practices", ["custom_domain"], unique=True)
    op.add_column("agent_runs", sa.Column("input_short", sa.String(200), nullable=True))
    op.add_column("agent_runs", sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("agent_runs", "tokens")
    op.drop_column("agent_runs", "input_short")
    op.drop_index("ix_practices_custom_domain", table_name="practices")
    op.drop_column("practices", "domain_confirmed_at")
    op.drop_column("practices", "custom_domain")
