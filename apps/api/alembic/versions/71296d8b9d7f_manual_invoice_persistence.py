"""manual invoice persistence

Revision ID: 71296d8b9d7f
Revises: 041
Create Date: 2026-09-15 16:43:56.313918

- tuition_invoices.kind: 'tuition' or 'manual'.
- tuition_invoices.manual_student_name: for walk-in manual invoices.
- tuition_invoices.unit_id: now nullable so manual invoices can be unlinked.
- tuition_invoice_lines.month_label: per-line month text used by manual invoices.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71296d8b9d7f'
down_revision: Union[str, None] = '041'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tuition_invoices",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="tuition"),
    )
    op.add_column(
        "tuition_invoices",
        sa.Column("manual_student_name", sa.String(length=255), nullable=True),
    )
    op.alter_column(
        "tuition_invoices",
        "unit_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.add_column(
        "tuition_invoice_lines",
        sa.Column("month_label", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tuition_invoice_lines", "month_label")
    op.alter_column(
        "tuition_invoices",
        "unit_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("tuition_invoices", "manual_student_name")
    op.drop_column("tuition_invoices", "kind")
