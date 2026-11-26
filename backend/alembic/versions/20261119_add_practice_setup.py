"""practice verification, structured details, page draft, therapist invites

Revision ID: 20261119_015
Revises: 20261118_014
Create Date: 2026-11-19 09:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20261119_015"
down_revision = "20261118_014"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("practices", sa.Column("verification_status", sa.String(24), nullable=False, server_default="draft"))
    for name, col in (("reviewer_note", sa.Text()), ("submitted_at", TZ), ("reviewed_at", TZ), ("city", sa.String(120)),
                      ("address", sa.Text()), ("approach", sa.Text()), ("fee_min", sa.Integer()), ("fee_max", sa.Integer()),
                      ("hours", sa.Text()), ("years_operating", sa.Integer()), ("page_tagline", sa.String(200)),
                      ("page_text", sa.Text()), ("page_source", sa.String(16)), ("page_inputs", sa.JSON()),
                      ("page_updated_at", TZ)):
        op.add_column("practices", sa.Column(name, col, nullable=True))
    for name in ("specialisations", "languages", "session_formats"):
        op.add_column("practices", sa.Column(name, sa.JSON(), nullable=False, server_default="[]"))
    # `verified` follows the status, so public listings of existing practices do not change
    op.execute("UPDATE practices SET verification_status = 'verified' WHERE verified")

    op.add_column("therapist_profiles", sa.Column("left_practice_at", TZ, nullable=True))

    op.create_table(
        "practice_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_id", sa.Integer(), sa.ForeignKey("practices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("decided_at", TZ, nullable=True),
        sa.Column("accepted_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("practice_id", "idempotency_key", name="uq_practice_invite_idempotency"),
    )
    op.create_index("ix_practice_invites_id", "practice_invites", ["id"])
    op.create_index("ix_practice_invites_practice_id", "practice_invites", ["practice_id"])
    op.create_index("ix_practice_invites_email", "practice_invites", ["email"])


def downgrade() -> None:
    op.drop_table("practice_invites")
    op.drop_column("therapist_profiles", "left_practice_at")
    for name in ("specialisations", "languages", "session_formats", "reviewer_note", "submitted_at", "reviewed_at", "city",
                 "address", "approach", "fee_min", "fee_max", "hours", "years_operating", "page_tagline", "page_text",
                 "page_source", "page_inputs", "page_updated_at", "verification_status"):
        op.drop_column("practices", name)
