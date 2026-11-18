"""invoice currency, second remark and other-currency commission

Revision ID: 056
Revises: 055
Create Date: 2026-11-18

Adds ``tuition_invoices.top_notes`` (Remark 1), ``tuition_invoices.currency``
and ``tuition_receipts.currency`` (default HKD), and the nullable JSON
``payroll_records.commission_other`` (non-HKD commission per currency).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tuition_invoices") as batch:
        batch.add_column(sa.Column("top_notes", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="HKD")
        )
    with op.batch_alter_table("tuition_receipts") as batch:
        batch.add_column(
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="HKD")
        )
    with op.batch_alter_table("payroll_records") as batch:
        batch.add_column(sa.Column("commission_other", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("payroll_records") as batch:
        batch.drop_column("commission_other")
    with op.batch_alter_table("tuition_receipts") as batch:
        batch.drop_column("currency")
    with op.batch_alter_table("tuition_invoices") as batch:
        batch.drop_column("currency")
        batch.drop_column("top_notes")
