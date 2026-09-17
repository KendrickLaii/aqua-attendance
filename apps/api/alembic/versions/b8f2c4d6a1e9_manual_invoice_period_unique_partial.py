"""manual invoices exempt from unit/period uniqueness

The (unit_id, period_start, period_end) unique rule exists so Generate cannot
create two tuition invoices for one student in one month. Manual invoices set
period_start == period_end == issue date, so the constraint also blocked a
student from ever getting two manual invoices on the same day — including the
normal void → re-issue flow. Replace the constraint with a partial unique
index that only applies to kind = 'tuition'.

Revision ID: b8f2c4d6a1e9
Revises: a1c9e4d7f2b3
Create Date: 2026-09-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8f2c4d6a1e9'
down_revision: Union[str, None] = 'a1c9e4d7f2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tuition_invoices') as batch:
        batch.drop_constraint('uq_tuition_invoices_unit_period', type_='unique')
        batch.create_index(
            'uq_tuition_invoices_unit_period',
            ['unit_id', 'period_start', 'period_end'],
            unique=True,
            postgresql_where=sa.text("kind = 'tuition'"),
            sqlite_where=sa.text("kind = 'tuition'"),
        )


def downgrade() -> None:
    with op.batch_alter_table('tuition_invoices') as batch:
        batch.drop_index(
            'uq_tuition_invoices_unit_period',
            postgresql_where=sa.text("kind = 'tuition'"),
            sqlite_where=sa.text("kind = 'tuition'"),
        )
        batch.create_unique_constraint(
            'uq_tuition_invoices_unit_period',
            ['unit_id', 'period_start', 'period_end'],
        )
