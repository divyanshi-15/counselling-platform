"""public contact form messages

Revision ID: 20261123_019
Revises: 20261122_018
Create Date: 2026-11-23 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261123_019"
down_revision = "20261122_018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("high_priority", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_contact_messages_id", "contact_messages", ["id"])


def downgrade() -> None:
    op.drop_index("ix_contact_messages_id", table_name="contact_messages")
    op.drop_table("contact_messages")
