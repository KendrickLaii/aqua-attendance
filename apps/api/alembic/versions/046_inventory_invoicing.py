"""inventory phase 5: invoices, receipts, credit notes

Revision ID: 046
Revises: 045
Create Date: 2026-10-16

- inventory_invoices + inventory_invoice_lines (accounting docs over delivery
  orders; invoice_no allocated at issue; credited_qty tracks credit notes).
- inventory_receipts (posted/void, amount <= invoice balance).
- inventory_credit_notes + inventory_credit_note_lines (draft/confirmed/void;
  restock lines put stock back).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invoice_no", sa.String(50), nullable=True),
        sa.Column(
            "do_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "so_id",
            sa.Uuid(),
            sa.ForeignKey("sales_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("buyer_name", sa.String(255), nullable=False),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_invoices_invoice_no", "inventory_invoices", ["invoice_no"], unique=True)
    op.create_index("ix_inventory_invoices_do_id", "inventory_invoices", ["do_id"])
    op.create_index("ix_inventory_invoices_so_id", "inventory_invoices", ["so_id"])
    op.create_index("ix_inventory_invoices_customer_id", "inventory_invoices", ["customer_id"])
    op.create_index("ix_inventory_invoices_location_id", "inventory_invoices", ["location_id"])

    op.create_table(
        "inventory_invoice_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "do_line_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_order_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "so_line_id",
            sa.Uuid(),
            sa.ForeignKey("sales_order_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku_code", sa.String(100), nullable=False),
        sa.Column("name_zh", sa.String(255), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("credited_qty", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_inventory_invoice_lines_invoice_id", "inventory_invoice_lines", ["invoice_id"])
    op.create_index("ix_inventory_invoice_lines_do_line_id", "inventory_invoice_lines", ["do_line_id"])
    op.create_index("ix_inventory_invoice_lines_so_line_id", "inventory_invoice_lines", ["so_line_id"])
    op.create_index("ix_inventory_invoice_lines_item_id", "inventory_invoice_lines", ["item_id"])

    op.create_table(
        "inventory_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("receipt_no", sa.String(50), nullable=False),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_by", sa.String(30), nullable=False),
        sa.Column("reference_no", sa.String(100), nullable=True),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_receipts_receipt_no", "inventory_receipts", ["receipt_no"], unique=True)
    op.create_index("ix_inventory_receipts_invoice_id", "inventory_receipts", ["invoice_id"])
    op.create_index("ix_inventory_receipts_customer_id", "inventory_receipts", ["customer_id"])
    op.create_index("ix_inventory_receipts_location_id", "inventory_receipts", ["location_id"])

    op.create_table(
        "inventory_credit_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scn_no", sa.String(50), nullable=False),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("credit_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_credit_notes_scn_no", "inventory_credit_notes", ["scn_no"], unique=True)
    op.create_index("ix_inventory_credit_notes_invoice_id", "inventory_credit_notes", ["invoice_id"])
    op.create_index("ix_inventory_credit_notes_customer_id", "inventory_credit_notes", ["customer_id"])
    op.create_index("ix_inventory_credit_notes_location_id", "inventory_credit_notes", ["location_id"])

    op.create_table(
        "inventory_credit_note_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "scn_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_credit_notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_line_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_invoice_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("restock", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_inventory_credit_note_lines_scn_id", "inventory_credit_note_lines", ["scn_id"])
    op.create_index(
        "ix_inventory_credit_note_lines_invoice_line_id",
        "inventory_credit_note_lines",
        ["invoice_line_id"],
    )
    op.create_index("ix_inventory_credit_note_lines_item_id", "inventory_credit_note_lines", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_credit_note_lines_item_id", table_name="inventory_credit_note_lines")
    op.drop_index("ix_inventory_credit_note_lines_invoice_line_id", table_name="inventory_credit_note_lines")
    op.drop_index("ix_inventory_credit_note_lines_scn_id", table_name="inventory_credit_note_lines")
    op.drop_table("inventory_credit_note_lines")
    op.drop_index("ix_inventory_credit_notes_location_id", table_name="inventory_credit_notes")
    op.drop_index("ix_inventory_credit_notes_customer_id", table_name="inventory_credit_notes")
    op.drop_index("ix_inventory_credit_notes_invoice_id", table_name="inventory_credit_notes")
    op.drop_index("ix_inventory_credit_notes_scn_no", table_name="inventory_credit_notes")
    op.drop_table("inventory_credit_notes")
    op.drop_index("ix_inventory_receipts_location_id", table_name="inventory_receipts")
    op.drop_index("ix_inventory_receipts_customer_id", table_name="inventory_receipts")
    op.drop_index("ix_inventory_receipts_invoice_id", table_name="inventory_receipts")
    op.drop_index("ix_inventory_receipts_receipt_no", table_name="inventory_receipts")
    op.drop_table("inventory_receipts")
    op.drop_index("ix_inventory_invoice_lines_item_id", table_name="inventory_invoice_lines")
    op.drop_index("ix_inventory_invoice_lines_so_line_id", table_name="inventory_invoice_lines")
    op.drop_index("ix_inventory_invoice_lines_do_line_id", table_name="inventory_invoice_lines")
    op.drop_index("ix_inventory_invoice_lines_invoice_id", table_name="inventory_invoice_lines")
    op.drop_table("inventory_invoice_lines")
    op.drop_index("ix_inventory_invoices_location_id", table_name="inventory_invoices")
    op.drop_index("ix_inventory_invoices_customer_id", table_name="inventory_invoices")
    op.drop_index("ix_inventory_invoices_so_id", table_name="inventory_invoices")
    op.drop_index("ix_inventory_invoices_do_id", table_name="inventory_invoices")
    op.drop_index("ix_inventory_invoices_invoice_no", table_name="inventory_invoices")
    op.drop_table("inventory_invoices")
