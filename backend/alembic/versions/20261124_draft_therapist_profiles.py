"""therapist profiles may exist without a practice; backfill drafts for therapist users

Revision ID: 20261124_020
Revises: 20261123_019
Create Date: 2026-11-24 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261124_020"
down_revision = "20261123_019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("therapist_profiles", "practice_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("therapist_profiles", "fee", existing_type=sa.Integer(), nullable=True)
    op.execute(
        """
        INSERT INTO therapist_profiles (user_id, bio, approaches, languages, specialisations, verified, verification_status,
                                        credentials, years_experience, review_count)
        SELECT u.id, '', '[]'::json, '[]'::json, '[]'::json, false, 'draft', '', 0, 0
        FROM users u
        WHERE u.role = 'therapist' AND NOT EXISTS (SELECT 1 FROM therapist_profiles t WHERE t.user_id = u.id)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM therapist_profiles WHERE practice_id IS NULL")
    op.execute("UPDATE therapist_profiles SET fee = 0 WHERE fee IS NULL")
    op.alter_column("therapist_profiles", "fee", existing_type=sa.Integer(), nullable=False)
    op.alter_column("therapist_profiles", "practice_id", existing_type=sa.Integer(), nullable=False)
