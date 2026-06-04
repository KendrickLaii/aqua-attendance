"""Add recorded_at indexes on attendance_events for list/export/stats performance.

The attendance_events table grows indefinitely. List, CSV export and stats
queries sort by ``recorded_at`` (DESC) and filter by date ranges, often scoped
by ``product_id``. Without these indexes the planner falls back to a full table
scan + sort once the table is large.

- ix_attendance_events_recorded_at: speeds global, date-range and ORDER BY
  recorded_at queries (no product filter).
- ix_attendance_events_product_recorded: composite for the common
  "one product's history, newest first" access pattern.

Revision ID: 013
Revises: 012
Create Date: 2026-06-04 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_attendance_events_recorded_at",
        "attendance_events",
        ["recorded_at"],
    )
    op.create_index(
        "ix_attendance_events_product_recorded",
        "attendance_events",
        ["product_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_attendance_events_product_recorded",
        table_name="attendance_events",
    )
    op.drop_index(
        "ix_attendance_events_recorded_at",
        table_name="attendance_events",
    )
