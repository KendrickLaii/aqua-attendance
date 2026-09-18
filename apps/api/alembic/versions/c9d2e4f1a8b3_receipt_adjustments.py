"""receipt adjustments

Revision ID: c9d2e4f1a8b3
Revises: a7f3c1e8d4b2
Create Date: 2026-09-18 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d2e4f1a8b3"
down_revision: Union[str, None] = "a7f3c1e8d4b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tuition_receipts",
        sa.Column("adjustments", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("tuition_receipts", "adjustments")
