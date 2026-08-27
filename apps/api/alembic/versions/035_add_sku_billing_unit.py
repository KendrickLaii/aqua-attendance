"""add billing_unit to course_skus

Revision ID: 035
Revises: 034
Create Date: 2026-08-27

One billing method per class offering: monthly (月費) or per_session (堂費).
Existing SKUs default to monthly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course_skus",
        sa.Column("billing_unit", sa.String(length=20), nullable=False, server_default="monthly"),
    )


def downgrade() -> None:
    op.drop_column("course_skus", "billing_unit")
