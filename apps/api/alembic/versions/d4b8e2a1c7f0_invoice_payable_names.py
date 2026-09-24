"""add payable_to_name and payee_name on tuition invoices

Printed on credit-note refund slips (CHEQUE PAYABLE TO / NAME).

Revision ID: d4b8e2a1c7f0
Revises: c9d2e4f1a8b3
Create Date: 2026-09-24 14:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4b8e2a1c7f0"
down_revision: Union[str, None] = "c9d2e4f1a8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tuition_invoices", sa.Column("payable_to_name", sa.String(length=255), nullable=True))
    op.add_column("tuition_invoices", sa.Column("payee_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("tuition_invoices", "payee_name")
    op.drop_column("tuition_invoices", "payable_to_name")
