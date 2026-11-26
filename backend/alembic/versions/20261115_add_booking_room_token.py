"""add bookings.room_token

Revision ID: 20261115_009
Revises: 20261114_008
Create Date: 2026-11-15 09:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_009"
down_revision = "20261114_008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("room_token", sa.String(64), nullable=True))
    # one fresh random uuid per row (gen_random_uuid() is volatile, so evaluated per row)
    op.execute("UPDATE bookings SET room_token = replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')")
    op.alter_column("bookings", "room_token", nullable=False)
    op.create_unique_constraint("uq_bookings_room_token", "bookings", ["room_token"])


def downgrade() -> None:
    op.drop_constraint("uq_bookings_room_token", "bookings", type_="unique")
    op.drop_column("bookings", "room_token")
