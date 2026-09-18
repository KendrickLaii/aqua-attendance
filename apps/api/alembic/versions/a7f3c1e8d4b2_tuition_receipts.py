"""tuition receipts

Revision ID: a7f3c1e8d4b2
Revises: e5a1c3d7f9b2
Create Date: 2026-09-18 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7f3c1e8d4b2"
down_revision: Union[str, None] = "e5a1c3d7f9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tuition_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("payer_name", sa.String(length=255), nullable=True),
        sa.Column("paid_by", sa.String(length=100), nullable=False),
        sa.Column("receipt_no", sa.String(length=50), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "receipt_no", name="uq_tuition_receipts_location_receipt_no"),
    )
    op.create_index("ix_tuition_receipts_location_id", "tuition_receipts", ["location_id"])
    op.create_index("ix_tuition_receipts_unit_id", "tuition_receipts", ["unit_id"])
    op.create_index("ix_tuition_receipts_receipt_date", "tuition_receipts", ["receipt_date"])

    op.create_table(
        "tuition_receipt_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_posted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["receipt_id"], ["tuition_receipts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["tuition_invoices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tuition_receipt_invoices_receipt_id", "tuition_receipt_invoices", ["receipt_id"])
    op.create_index("ix_tuition_receipt_invoices_invoice_id", "tuition_receipt_invoices", ["invoice_id"])
    op.create_index(
        "uq_tuition_receipt_invoices_posted_invoice",
        "tuition_receipt_invoices",
        ["invoice_id"],
        unique=True,
        postgresql_where=sa.text("is_posted"),
        sqlite_where=sa.text("is_posted"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_tuition_receipt_invoices_posted_invoice",
        table_name="tuition_receipt_invoices",
        postgresql_where=sa.text("is_posted"),
        sqlite_where=sa.text("is_posted"),
    )
    op.drop_index("ix_tuition_receipt_invoices_invoice_id", table_name="tuition_receipt_invoices")
    op.drop_index("ix_tuition_receipt_invoices_receipt_id", table_name="tuition_receipt_invoices")
    op.drop_table("tuition_receipt_invoices")
    op.drop_index("ix_tuition_receipts_receipt_date", table_name="tuition_receipts")
    op.drop_index("ix_tuition_receipts_unit_id", table_name="tuition_receipts")
    op.drop_index("ix_tuition_receipts_location_id", table_name="tuition_receipts")
    op.drop_table("tuition_receipts")
