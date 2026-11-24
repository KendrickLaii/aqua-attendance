"""store course sku meeting days as a list

Revision ID: 059
Revises: 058
Create Date: 2026-11-24

Some line items kept meeting_weekdays as {}. The API expects a list, so
listing those rows returned 500.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE course_skus SET meeting_weekdays = '[]'::json "
        "WHERE jsonb_typeof(meeting_weekdays::jsonb) = 'object'"
    )


def downgrade() -> None:
    pass
