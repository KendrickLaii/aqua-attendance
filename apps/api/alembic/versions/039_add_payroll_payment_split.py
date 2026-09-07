"""add cheque/cash payment split to payroll_records

Revision ID: 039
Revises: 038
Create Date: 2026-09-07

Stores how a paid slip was settled: cheque number, cheque amount, and cash amount.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payroll_records",
        sa.Column("cheque_number", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "payroll_records",
        sa.Column("cheque_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "payroll_records",
        sa.Column("cash_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("payroll_records", "cash_amount")
    op.drop_column("payroll_records", "cheque_amount")
    op.drop_column("payroll_records", "cheque_number")
