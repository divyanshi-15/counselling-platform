"""add exercises (fixed library), assignments, checkins

Revision ID: 20261114_006
Revises: 20261114_005
Create Date: 2026-11-14 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20261114_006"
down_revision = "20261114_005"
branch_labels = None
depends_on = None

THOUGHT_RECORD = {
    "intro": "Slow down one strong feeling and look at the thought behind it. Write a few words in each box.",
    "fields": [
        {"id": "situation", "label": "What was happening?", "type": "text", "required": True},
        {"id": "thought", "label": "What thought went through your mind?", "type": "text", "required": True},
        {"id": "feeling_before", "label": "How strong was the feeling? (0 = none, 10 = very strong)", "type": "scale", "required": True},
        {"id": "evidence_for", "label": "What supports this thought?", "type": "text", "required": False},
        {"id": "evidence_against", "label": "What does not fit this thought?", "type": "text", "required": False},
        {"id": "balanced_thought", "label": "A more balanced way to see it", "type": "text", "required": False},
        {"id": "feeling_after", "label": "How strong is the feeling now? (0-10)", "type": "scale", "required": False},
    ],
}
WORRY_POSTPONEMENT = {
    "intro": "Write every worry down now (a brain dump), then choose a set worry time later today to come back to them.",
    "fields": [
        {"id": "worries", "label": "Brain dump: list the worries on your mind", "type": "text", "required": True},
        {"id": "can_act_now", "label": "Is there one small step you can take right now?", "type": "text", "required": False},
        {"id": "worry_time", "label": "When will your worry time be? (for example 6:30 pm, 15 minutes)", "type": "text", "required": True},
        {"id": "feeling_after", "label": "How heavy do the worries feel now? (0 = light, 10 = very heavy)", "type": "scale", "required": False},
    ],
}


def upgrade() -> None:
    exercises = op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("kb_slug", sa.String(length=120), nullable=True),
        sa.Column("title_en", sa.String(length=255), nullable=False),
        sa.Column("template_en", sa.JSON(), nullable=False),
        sa.Column("title_hi", sa.String(length=255), nullable=True),
        sa.Column("template_hi", sa.JSON(), nullable=True),
        sa.Column("title_kn", sa.String(length=255), nullable=True),
        sa.Column("template_kn", sa.JSON(), nullable=True),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_exercises_id", "exercises", ["id"])
    op.bulk_insert(exercises, [
        {"slug": "thought_record", "kb_slug": "thought-record", "title_en": "Thought record", "template_en": THOUGHT_RECORD},
        {"slug": "worry_postponement", "kb_slug": "worry-postponement",
         "title_en": "Worry postponement (brain dump)", "template_en": WORRY_POSTPONEMENT},
    ])
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("therapist_user_id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("pending_action_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pending_action_id"], ["pending_actions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("pending_action_id"),
    )
    op.create_index("ix_assignments_id", "assignments", ["id"])
    op.create_index("ix_assignments_client_id", "assignments", ["client_id"])
    op.create_index("ix_assignments_therapist_user_id", "assignments", ["therapist_user_id"])
    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("responses_json", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_checkins_id", "checkins", ["id"])
    op.create_index("ix_checkins_assignment_id", "checkins", ["assignment_id"])


def downgrade() -> None:
    op.drop_table("checkins")
    op.drop_table("assignments")
    op.drop_table("exercises")
