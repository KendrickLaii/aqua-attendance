"""add tuition invoices

Revision ID: 036
Revises: 035
Create Date: 2026-08-27

Monthly student tuition invoices with frozen SKU price and billing_unit
on each line. One invoice per student per calendar month.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tuition_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id", "period_start", "period_end", name="uq_tuition_invoices_unit_period"),
    )
    op.create_index("ix_tuition_invoices_unit_id", "tuition_invoices", ["unit_id"])
    op.create_index("ix_tuition_invoices_period_start", "tuition_invoices", ["period_start"])
    op.create_index("ix_tuition_invoices_period_end", "tuition_invoices", ["period_end"])

    op.create_table(
        "tuition_invoice_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=True),
        sa.Column("sku_id", sa.Uuid(), nullable=True),
        sa.Column("sku_code", sa.String(length=100), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("billing_unit", sa.String(length=20), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["tuition_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["course_enrollments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sku_id"], ["course_skus.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tuition_invoice_lines_invoice_id", "tuition_invoice_lines", ["invoice_id"])
    op.create_index("ix_tuition_invoice_lines_enrollment_id", "tuition_invoice_lines", ["enrollment_id"])
    op.create_index("ix_tuition_invoice_lines_sku_id", "tuition_invoice_lines", ["sku_id"])


def downgrade() -> None:
    op.drop_table("tuition_invoice_lines")
    op.drop_table("tuition_invoices")
