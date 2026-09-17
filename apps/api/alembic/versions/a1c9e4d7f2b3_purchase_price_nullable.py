"""enrollment purchase price nullable

Allows per_session enrollments (私補) to record purchased sessions without a
price — the price is set when the package is billed on a manual invoice.

Revision ID: a1c9e4d7f2b3
Revises: bfb6cd4eb3b9
Create Date: 2026-09-15 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9e4d7f2b3'
down_revision: Union[str, None] = 'bfb6cd4eb3b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'enrollment_purchases',
        'unit_price',
        existing_type=sa.Numeric(10, 2),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM enrollment_purchases WHERE unit_price IS NULL"))
    op.alter_column(
        'enrollment_purchases',
        'unit_price',
        existing_type=sa.Numeric(10, 2),
        nullable=False,
    )
