"""add staff_profiles.commission_rate (分成比例)

Staff commission percentage (0–100). NULL means the staff earns no
commission. Payroll generation sums that month's paid invoices whose
invoice-level Tutor (tuition_invoices.staff_name) matches the staff's
full_name and writes total × rate / 100 into adjustment_1.

Revision ID: e7b3f9a1c2d4
Revises: c5e8a2f4d6b1
Create Date: 2026-10-07 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b3f9a1c2d4'
down_revision: Union[str, None] = 'c5e8a2f4d6b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('staff_profiles', sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('staff_profiles', 'commission_rate')
