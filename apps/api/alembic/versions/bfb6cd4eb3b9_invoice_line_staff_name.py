"""invoice line staff name

Revision ID: bfb6cd4eb3b9
Revises: 7d340d0ce7de
Create Date: 2026-09-15 19:38:44.830283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfb6cd4eb3b9'
down_revision: Union[str, None] = '7d340d0ce7de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tuition_invoice_lines',
        sa.Column('staff_name', sa.String(length=255), nullable=True),
    )
    # Snapshot the class's current teacher onto existing lines.
    op.execute(
        sa.text(
            """
            UPDATE tuition_invoice_lines l
            SET staff_name = u.full_name
            FROM course_skus s
            JOIN units u ON u.id = s.staff_id
            WHERE l.sku_id = s.id
            """
        )
    )


def downgrade() -> None:
    op.drop_column('tuition_invoice_lines', 'staff_name')
