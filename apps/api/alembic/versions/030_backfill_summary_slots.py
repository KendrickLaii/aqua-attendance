"""backfill attendance_summaries slots from hours

Revision ID: 030
Revises: 029
Create Date: 2026-07-17

Seed / pre-slot rows often have regular_hours and overtime_hours set but
regular_slots / ot_slots left at the column default of 0. Derive slots as
hours * 4 (1 slot = 15 minutes = 0.25h).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '030'
down_revision: Union[str, None] = '029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE attendance_summaries
        SET
            regular_slots = ROUND(COALESCE(regular_hours, 0) * 4),
            ot_slots = ROUND(COALESCE(overtime_hours, 0) * 4)
        WHERE regular_slots = 0
          AND ot_slots = 0
          AND (COALESCE(regular_hours, 0) > 0 OR COALESCE(overtime_hours, 0) > 0)
        """
    )


def downgrade() -> None:
    # Irreversible data backfill; leave slots as-is.
    pass
