"""add tuition_invoices.tutor_unit_id + payroll_records.commission_rate_snapshot + commission_pay

tutor_unit_id links an invoice's Tutor (開單人) to a staff unit so payroll
commission matches by id instead of by name; staff_name stays as the display
snapshot. commission_rate_snapshot freezes the rate used at payroll
generation so regenerating a draft record keeps the original rate.
commission_pay holds the computed commission as its own payroll row —
adjustment_1 reverts to a pure manual adjustment.

Revision ID: b9e4d2a7c1f5
Revises: e7b3f9a1c2d4
Create Date: 2026-10-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e4d2a7c1f5'
down_revision: Union[str, None] = 'e7b3f9a1c2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tuition_invoices',
        sa.Column('tutor_unit_id', sa.Uuid(), nullable=True),
    )
    # batch_alter_table emits plain ALTER on Postgres and a table rebuild on
    # SQLite, which cannot alter constraints/indexes in place.
    with op.batch_alter_table('tuition_invoices') as batch:
        batch.create_foreign_key(
            'fk_tuition_invoices_tutor_unit_id',
            'units',
            ['tutor_unit_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch.create_index(
            'ix_tuition_invoices_tutor_unit_id',
            ['tutor_unit_id'],
        )
    op.add_column(
        'payroll_records',
        sa.Column('commission_rate_snapshot', sa.Numeric(5, 2), nullable=True),
    )
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
    op.drop_column('payroll_records', 'commission_pay')
    op.drop_column('payroll_records', 'commission_rate_snapshot')
    with op.batch_alter_table('tuition_invoices') as batch:
        batch.drop_index('ix_tuition_invoices_tutor_unit_id')
        # SQLite rebuilds the table when the column is dropped, removing the
        # (unnamed-on-reflect) FK along with it.
        if op.get_context().dialect.name != 'sqlite':
            batch.drop_constraint(
                'fk_tuition_invoices_tutor_unit_id', type_='foreignkey'
            )
        batch.drop_column('tutor_unit_id')
