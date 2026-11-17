"""add therapist profile credentials, experience, rating, specialisations

Revision ID: 20261117_012
Revises: 20261115_011
Create Date: 2026-11-17 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261117_012"
down_revision = "20261115_011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapist_profiles", sa.Column("credentials", sa.String(255), nullable=False, server_default=""))
    op.add_column("therapist_profiles", sa.Column("years_experience", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("therapist_profiles", sa.Column("rating", sa.Float(), nullable=True))
    op.add_column("therapist_profiles", sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("therapist_profiles", sa.Column("specialisations", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    for col in ("specialisations", "review_count", "rating", "years_experience", "credentials"):
        op.drop_column("therapist_profiles", col)
