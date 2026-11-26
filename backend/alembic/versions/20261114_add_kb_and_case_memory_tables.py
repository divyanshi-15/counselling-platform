"""add knowledge base and per-client case memory tables

Revision ID: 20261114_004
Revises: 20261114_003
Create Date: 2026-11-14 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "20261114_004"
down_revision = "20261114_003"
branch_labels = None
depends_on = None

def _tsv() -> sa.Computed:
    return sa.Computed("to_tsvector('english', text)", persisted=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("approach", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("source_inspired_by", sa.Text(), nullable=False),
        sa.Column("licence", sa.String(length=100), nullable=False),
        sa.Column("reviewed_by", sa.String(length=150), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_kb_documents_id", "kb_documents", ["id"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("approach", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("topic_tags", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), _tsv(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["kb_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_chunks_id", "kb_chunks", ["id"])
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])
    op.create_index("ix_kb_chunks_approach_language", "kb_chunks", ["approach", "language"])
    op.create_index("ix_kb_chunks_tsv", "kb_chunks", ["tsv"], postgresql_using="gin")

    op.create_table(
        "case_memory_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), _tsv(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_memory_chunks_id", "case_memory_chunks", ["id"])
    op.create_index("ix_case_memory_client_therapist", "case_memory_chunks", ["client_id", "therapist_user_id"])
    op.create_index("ix_case_memory_tsv", "case_memory_chunks", ["tsv"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_table("case_memory_chunks")
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
