"""add adjustment_1 and adjustment_2 to payroll_records

Revision ID: 027
Revises: 026
Create Date: 2026-07-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '027'
down_revision: Union[str, None] = '026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payroll_records', sa.Column('adjustment_1', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('payroll_records', sa.Column('adjustment_2', sa.Numeric(10, 2), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('payroll_records', 'adjustment_2')
    op.drop_column('payroll_records', 'adjustment_1')
