"""drop total_break_minutes from attendance_summaries

Revision ID: 029
Revises: 028
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '029'
down_revision: Union[str, None] = '028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('attendance_summaries', 'total_break_minutes')


def downgrade() -> None:
    op.add_column(
        'attendance_summaries',
        sa.Column('total_break_minutes', sa.Integer(), nullable=False, server_default='0'),
    )
