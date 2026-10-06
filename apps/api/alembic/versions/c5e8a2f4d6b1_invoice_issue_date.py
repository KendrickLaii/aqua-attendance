"""add issue_date on tuition invoices

Manual invoices used period_start == period_end == typed date, so a bill
opened on 30 Sept for October landed in September. The typed date now lives
in issue_date and period_start/period_end hold the billing month. Existing
manual rows keep their period (the date's day) and copy it into issue_date.

Revision ID: c5e8a2f4d6b1
Revises: a3d5f7b9c1e2
Create Date: 2026-10-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c5e8a2f4d6b1"
down_revision: Union[str, None] = "a3d5f7b9c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tuition_invoices", sa.Column("issue_date", sa.Date(), nullable=True))
    op.execute("UPDATE tuition_invoices SET issue_date = period_start WHERE kind = 'manual'")


def downgrade() -> None:
    op.drop_column("tuition_invoices", "issue_date")
