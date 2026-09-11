"""add invoice_no and issued_at to tuition_invoices

Revision ID: 040
Revises: 039
Create Date: 2026-09-11

Stores the handwritten-style serial number staff type when issuing a bill
(編號 on the printed invoice) and when the bill was issued.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tuition_invoices",
        sa.Column("invoice_no", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "tuition_invoices",
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tuition_invoices", "issued_at")
    op.drop_column("tuition_invoices", "invoice_no")
