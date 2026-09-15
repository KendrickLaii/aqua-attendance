"""add staff_id to course_skus and unit_price to course_enrollments

Revision ID: 041
Revises: 040
Create Date: 2026-09-15

- course_skus.staff_id: the staff member / teacher assigned to the class.
- course_enrollments.unit_price: per-student price override for classes
  with no fixed price (e.g. 私補). Generator bills this when the SKU has
  no price of its own.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "course_skus",
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("units.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_course_skus_staff_id", "course_skus", ["staff_id"])
    op.add_column(
        "course_enrollments",
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=True),
    )
    op.create_table(
        "invoice_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("next_no", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_tuition_invoices_invoice_no",
        "tuition_invoices",
        ["invoice_no"],
        unique=True,
    )
    # Seed the counter past the highest numeric invoice_no already in use.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT invoice_no FROM tuition_invoices WHERE invoice_no IS NOT NULL")
    ).scalars()
    max_no = max((int(v) for v in rows if str(v).strip().isdigit()), default=0)
    bind.execute(
        sa.text("INSERT INTO invoice_counters (id, next_no) VALUES (1, :n)"),
        {"n": max_no + 1},
    )


def downgrade() -> None:
    op.drop_index("ix_tuition_invoices_invoice_no", table_name="tuition_invoices")
    op.drop_table("invoice_counters")
    op.drop_column("course_enrollments", "unit_price")
    op.drop_index("ix_course_skus_staff_id", table_name="course_skus")
    op.drop_column("course_skus", "staff_id")
