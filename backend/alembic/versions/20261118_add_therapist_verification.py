"""therapist verification status, education, licenses, verification documents

Revision ID: 20261118_014
Revises: 20261117_013
Create Date: 2026-11-18 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261118_014"
down_revision = "20261117_013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapist_profiles", sa.Column("verification_status", sa.String(24), nullable=False, server_default="draft"))
    op.add_column("therapist_profiles", sa.Column("reviewer_note", sa.Text(), nullable=True))
    op.add_column("therapist_profiles", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("therapist_profiles", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE therapist_profiles SET verification_status = 'verified' WHERE verified")

    op.create_table(
        "therapist_education",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("therapist_id", sa.Integer(), sa.ForeignKey("therapist_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("degree", sa.String(150), nullable=False),
        sa.Column("institution", sa.String(200), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
    )
    op.create_index("ix_therapist_education_therapist_id", "therapist_education", ["therapist_id"])
    op.create_index("ix_therapist_education_id", "therapist_education", ["id"])

    op.create_table(
        "therapist_licenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("therapist_id", sa.Integer(), sa.ForeignKey("therapist_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("license_type", sa.String(100), nullable=False),
        sa.Column("registration_body", sa.String(150), nullable=False),
        sa.Column("registration_number", sa.String(60), nullable=False),
        sa.Column("issue_year", sa.Integer(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
    )
    op.create_index("ix_therapist_licenses_therapist_id", "therapist_licenses", ["therapist_id"])
    op.create_index("ix_therapist_licenses_id", "therapist_licenses", ["id"])

    op.create_table(
        "verification_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_type", sa.String(32), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(64), nullable=False, unique=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_documents_id", "verification_documents", ["id"])
    op.create_index("ix_verification_documents_owner", "verification_documents", ["owner_type", "owner_id"])


def downgrade() -> None:
    op.drop_table("verification_documents")
    op.drop_table("therapist_licenses")
    op.drop_table("therapist_education")
    for col in ("reviewed_at", "submitted_at", "reviewer_note", "verification_status"):
        op.drop_column("therapist_profiles", col)
