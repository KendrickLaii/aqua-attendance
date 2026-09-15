"""enrollment_purchases

Revision ID: 7d340d0ce7de
Revises: f5d44789754d
Create Date: 2026-09-15 17:21:49.606999

- Create enrollment_purchases to record each top-up/purchase for per_session classes.
- Migrate existing per_session course_enrollments.purchased_quantity into a purchase.
- Link already-billed lines to those purchases so they are not re-billed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d340d0ce7de'
down_revision: Union[str, None] = 'f5d44789754d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'enrollment_purchases',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('enrollment_id', sa.Uuid(), nullable=False),
        sa.Column('purchased_quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('purchased_at', sa.Date(), nullable=False),
        sa.Column('billed_invoice_line_id', sa.Uuid(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['billed_invoice_line_id'], ['tuition_invoice_lines.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(['enrollment_id'], ['course_enrollments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_enrollment_purchases_billed_invoice_line_id'),
        'enrollment_purchases',
        ['billed_invoice_line_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_enrollment_purchases_enrollment_id'),
        'enrollment_purchases',
        ['enrollment_id'],
        unique=False,
    )

    # Migrate existing per_session purchased_quantity into a purchase record.
    op.execute(
        sa.text(
            """
            INSERT INTO enrollment_purchases (
                id, enrollment_id, purchased_quantity, unit_price, purchased_at,
                billed_invoice_line_id, notes, created_at
            )
            SELECT
                gen_random_uuid(),
                e.id,
                e.purchased_quantity,
                COALESCE(e.unit_price, s.price),
                e.enrolled_at,
                (
                    SELECT l.id
                    FROM tuition_invoice_lines l
                    JOIN tuition_invoices i ON i.id = l.invoice_id
                    WHERE l.enrollment_id = e.id
                      AND i.status != 'void'
                    LIMIT 1
                ),
                e.notes,
                NOW()
            FROM course_enrollments e
            JOIN course_skus s ON s.id = e.sku_id
            WHERE s.billing_unit = 'per_session'
              AND e.purchased_quantity IS NOT NULL
              AND COALESCE(e.unit_price, s.price) IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_enrollment_purchases_enrollment_id'), table_name='enrollment_purchases')
    op.drop_index(op.f('ix_enrollment_purchases_billed_invoice_line_id'), table_name='enrollment_purchases')
    op.drop_table('enrollment_purchases')
