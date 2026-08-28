"""add meeting_weekdays to course_skus

Revision ID: 037
Revises: 036
Create Date: 2026-08-28

Class meeting days (monday–sunday) used to count 堂費 sessions in a month.
Empty list means not configured; generate still uses quantity 1.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course_skus",
        sa.Column("meeting_weekdays", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )


def downgrade() -> None:
    op.drop_column("course_skus", "meeting_weekdays")
