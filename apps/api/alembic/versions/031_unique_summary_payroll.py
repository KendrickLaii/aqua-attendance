"""Add unique constraints for summaries and payroll.

Revision ID: 031
Revises: 030
Create Date: 2026-07-17

Prevents duplicate daily summaries per product/date and duplicate payroll
rows per product/period. Deduplicates any existing rows before adding
constraints (keeps the newest updated_at, then highest id).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM attendance_summaries
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY product_id, summary_date
                           ORDER BY updated_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM attendance_summaries
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.execute(
        """
        DELETE FROM payroll_records
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY product_id, payroll_period_start, payroll_period_end
                           ORDER BY updated_at DESC NULLS LAST, id DESC
                       ) AS rn
                FROM payroll_records
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_attendance_summaries_product_date",
        "attendance_summaries",
        ["product_id", "summary_date"],
    )
    op.create_unique_constraint(
        "uq_payroll_records_product_period",
        "payroll_records",
        ["product_id", "payroll_period_start", "payroll_period_end"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_payroll_records_product_period",
        "payroll_records",
        type_="unique",
    )
    op.drop_constraint(
        "uq_attendance_summaries_product_date",
        "attendance_summaries",
        type_="unique",
    )
