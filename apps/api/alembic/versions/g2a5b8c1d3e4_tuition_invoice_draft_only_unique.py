"""one open draft tuition invoice per student per period

Generate now uses delta billing: locked (issued/paid) invoices are never
touched, and anything not covered by them goes on a supplementary draft for
the same month. The old partial unique index (kind = 'tuition') blocked a
second tuition invoice per student+month entirely, so it could not coexist
with an issued bill. Narrow the index to drafts only — at most one open
draft per student per period, any number of issued/paid/void bills.

Revision ID: g2a5b8c1d3e4
Revises: d1f6b3e8a9c2
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2a5b8c1d3e4'
down_revision: Union[str, None] = 'd1f6b3e8a9c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tuition_invoices') as batch:
        batch.drop_index(
            'uq_tuition_invoices_unit_period',
            postgresql_where=sa.text("kind = 'tuition'"),
            sqlite_where=sa.text("kind = 'tuition'"),
        )
        batch.create_index(
            'uq_tuition_invoices_unit_period',
            ['unit_id', 'period_start', 'period_end'],
            unique=True,
            postgresql_where=sa.text("kind = 'tuition' AND status = 'draft'"),
            sqlite_where=sa.text("kind = 'tuition' AND status = 'draft'"),
        )


def downgrade() -> None:
    with op.batch_alter_table('tuition_invoices') as batch:
        batch.drop_index(
            'uq_tuition_invoices_unit_period',
            postgresql_where=sa.text("kind = 'tuition' AND status = 'draft'"),
            sqlite_where=sa.text("kind = 'tuition' AND status = 'draft'"),
        )
        batch.create_index(
            'uq_tuition_invoices_unit_period',
            ['unit_id', 'period_start', 'period_end'],
            unique=True,
            postgresql_where=sa.text("kind = 'tuition'"),
            sqlite_where=sa.text("kind = 'tuition'"),
        )
