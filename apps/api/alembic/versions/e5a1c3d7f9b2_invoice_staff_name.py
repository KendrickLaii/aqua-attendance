"""add tuition_invoices.staff_name (開單人 / who issued the invoice)

Invoice-level staff name — the staff/teacher who opened the invoice, used
for commission records. Distinct from tuition_invoice_lines.staff_name,
which snapshots the class teacher per line. Not printed on the invoice.

Manual invoices set it at creation; generated tuition invoices can set it
on the Issue dialog via PATCH.

Revision ID: e5a1c3d7f9b2
Revises: c3e7a95b2d10
Create Date: 2026-09-17 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a1c3d7f9b2'
down_revision: Union[str, None] = 'c3e7a95b2d10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tuition_invoices', sa.Column('staff_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('tuition_invoices', 'staff_name')
