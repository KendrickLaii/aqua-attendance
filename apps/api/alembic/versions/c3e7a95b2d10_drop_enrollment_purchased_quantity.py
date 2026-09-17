"""drop course_enrollments.purchased_quantity; clean stale void purchase links

EnrollmentPurchase is now the single source of truth for per_session (堂費)
session counts. The generator stopped reading course_enrollments.purchased_quantity,
so the column is dead weight that could drift from the purchase rows.

Steps:
1. Backfill: any per_session enrollment that still has a quantity but no
   purchase row gets one (price may be NULL — set when billed).
2. Clear billed_invoice_line_id on purchases whose line sits on a voided
   invoice. Voiding now clears links directly, so this only fixes rows voided
   before that behaviour existed.
3. Drop the column.

Revision ID: c3e7a95b2d10
Revises: b8f2c4d6a1e9
Create Date: 2026-09-17 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e7a95b2d10'
down_revision: Union[str, None] = 'b8f2c4d6a1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO enrollment_purchases
                (id, enrollment_id, purchased_quantity, unit_price, purchased_at, notes, created_at)
            SELECT
                gen_random_uuid(),
                e.id,
                e.purchased_quantity,
                COALESCE(e.unit_price, s.price),
                COALESCE(e.start_date, e.enrolled_at),
                'Backfilled from enrollment.purchased_quantity',
                NOW()
            FROM course_enrollments e
            JOIN course_skus s ON s.id = e.sku_id
            WHERE s.billing_unit = 'per_session'
              AND e.purchased_quantity IS NOT NULL
              AND e.purchased_quantity > 0
              AND NOT EXISTS (
                  SELECT 1 FROM enrollment_purchases p WHERE p.enrollment_id = e.id
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE enrollment_purchases p
               SET billed_invoice_line_id = NULL
             WHERE p.billed_invoice_line_id IN (
                       SELECT l.id
                         FROM tuition_invoice_lines l
                         JOIN tuition_invoices i ON i.id = l.invoice_id
                        WHERE i.status = 'void'
                   )
            """
        )
    )
    op.drop_column('course_enrollments', 'purchased_quantity')


def downgrade() -> None:
    op.add_column(
        'course_enrollments',
        sa.Column('purchased_quantity', sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE course_enrollments e
               SET purchased_quantity = totals.qty
              FROM (
                    SELECT enrollment_id, SUM(purchased_quantity) AS qty
                      FROM enrollment_purchases
                     GROUP BY enrollment_id
                   ) AS totals
             WHERE totals.enrollment_id = e.id
            """
        )
    )
