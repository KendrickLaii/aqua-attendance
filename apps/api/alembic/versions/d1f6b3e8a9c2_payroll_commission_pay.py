"""add payroll_records.commission_pay

commission_pay holds the computed commission as its own payroll row so
adjustment_1 reverts to a pure manual adjustment:
gross = base + OT + holiday + commission_pay + adjustment_1.

Idempotent: an interim build of b9e4d2a7c1f5 already added this column on
some databases, so skip the ADD/DROP when the column state already matches.

Revision ID: d1f6b3e8a9c2
Revises: b9e4d2a7c1f5
Create Date: 2026-10-12 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f6b3e8a9c2'
down_revision: Union[str, None] = 'b9e4d2a7c1f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_commission_pay() -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col['name'] == 'commission_pay' for col in inspector.get_columns('payroll_records'))


def upgrade() -> None:
    if _has_commission_pay():
        return
    op.add_column(
        'payroll_records',
        sa.Column(
            'commission_pay',
            sa.Numeric(10, 2),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    if not _has_commission_pay():
        return
    with op.batch_alter_table('payroll_records') as batch:
        batch.drop_column('commission_pay')
