"""add purchased_quantity to course_enrollments

Revision ID: 038
Revises: 037
Create Date: 2026-09-04

per_session (堂費) enrollments now bill a fixed, admin-entered number of
sessions purchased at enrollment time, as a one-time charge — not a
recurring monthly amount, and no longer derived from attendance ∩
meeting_weekdays. monthly (月費) enrollments ignore this column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course_enrollments",
        sa.Column("purchased_quantity", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("course_enrollments", "purchased_quantity")
