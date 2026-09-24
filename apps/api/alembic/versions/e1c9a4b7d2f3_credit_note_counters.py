"""per-location credit note number series (RF0001)

Revision ID: e1c9a4b7d2f3
Revises: d4b8e2a1c7f0
Create Date: 2026-09-24 16:24:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1c9a4b7d2f3"
down_revision: Union[str, None] = "d4b8e2a1c7f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_note_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("next_no", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("location_id"),
    )
    op.create_index("ix_credit_note_counters_location_id", "credit_note_counters", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_note_counters_location_id", table_name="credit_note_counters")
    op.drop_table("credit_note_counters")
