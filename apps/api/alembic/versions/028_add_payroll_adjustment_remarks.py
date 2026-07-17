"""add adjustment remarks to payroll_records

Revision ID: 028
Revises: 027
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '028'
down_revision: Union[str, None] = '027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payroll_records', sa.Column('adjustment_1_remark', sa.Text(), nullable=True))
    op.add_column('payroll_records', sa.Column('adjustment_2_remark', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('payroll_records', 'adjustment_2_remark')
    op.drop_column('payroll_records', 'adjustment_1_remark')
