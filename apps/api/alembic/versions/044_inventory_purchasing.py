"""inventory phase 3: suppliers, purchase orders, goods receipts, purchase returns

Revision ID: 044
Revises: 043
Create Date: 2026-10-16

- inventory_counters: per-(location, doc_type) sequential document numbering.
- suppliers.
- purchase_orders + purchase_order_lines (sku/name frozen, per-line and
  header discount, total = sum(line amount) - header discount, floor 0).
- goods_receipts + goods_receipt_lines (optional po_line link; confirm adds
  stock and updates weighted avg_cost; void reverses stock).
- purchase_returns + purchase_return_lines (confirm removes stock).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("doc_type", sa.String(10), nullable=False),
        sa.Column("next_no", sa.Integer(), nullable=False),
        sa.UniqueConstraint("location_id", "doc_type", name="uq_inventory_counters_loc_type"),
    )
    op.create_index("ix_inventory_counters_location_id", "inventory_counters", ["location_id"])

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name_zh", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_suppliers_code", "suppliers", ["code"], unique=True)

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("po_no", sa.String(50), nullable=False),
        sa.Column(
            "supplier_id",
            sa.Uuid(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_orders_po_no", "purchase_orders", ["po_no"], unique=True)
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_location_id", "purchase_orders", ["location_id"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "po_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
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
        sa.Column("ordered_qty", sa.Integer(), nullable=False),
        sa.Column("received_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_purchase_order_lines_po_id", "purchase_order_lines", ["po_id"])
    op.create_index("ix_purchase_order_lines_item_id", "purchase_order_lines", ["item_id"])

    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("grn_no", sa.String(50), nullable=False),
        sa.Column(
            "po_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "supplier_id",
            sa.Uuid(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goods_receipts_grn_no", "goods_receipts", ["grn_no"], unique=True)
    op.create_index("ix_goods_receipts_po_id", "goods_receipts", ["po_id"])
    op.create_index("ix_goods_receipts_supplier_id", "goods_receipts", ["supplier_id"])
    op.create_index("ix_goods_receipts_location_id", "goods_receipts", ["location_id"])

    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "grn_id",
            sa.Uuid(),
            sa.ForeignKey("goods_receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "po_line_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_order_lines.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("ix_goods_receipt_lines_grn_id", "goods_receipt_lines", ["grn_id"])
    op.create_index("ix_goods_receipt_lines_po_line_id", "goods_receipt_lines", ["po_line_id"])
    op.create_index("ix_goods_receipt_lines_item_id", "goods_receipt_lines", ["item_id"])

    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("prt_no", sa.String(50), nullable=False),
        sa.Column(
            "supplier_id",
            sa.Uuid(),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "grn_id",
            sa.Uuid(),
            sa.ForeignKey("goods_receipts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_returns_prt_no", "purchase_returns", ["prt_no"], unique=True)
    op.create_index("ix_purchase_returns_supplier_id", "purchase_returns", ["supplier_id"])
    op.create_index("ix_purchase_returns_location_id", "purchase_returns", ["location_id"])
    op.create_index("ix_purchase_returns_grn_id", "purchase_returns", ["grn_id"])

    op.create_table(
        "purchase_return_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "prt_id",
            sa.Uuid(),
            sa.ForeignKey("purchase_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("ix_purchase_return_lines_prt_id", "purchase_return_lines", ["prt_id"])
    op.create_index("ix_purchase_return_lines_item_id", "purchase_return_lines", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_purchase_return_lines_item_id", table_name="purchase_return_lines")
    op.drop_index("ix_purchase_return_lines_prt_id", table_name="purchase_return_lines")
    op.drop_table("purchase_return_lines")
    op.drop_index("ix_purchase_returns_grn_id", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_location_id", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_supplier_id", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_prt_no", table_name="purchase_returns")
    op.drop_table("purchase_returns")
    op.drop_index("ix_goods_receipt_lines_item_id", table_name="goods_receipt_lines")
    op.drop_index("ix_goods_receipt_lines_po_line_id", table_name="goods_receipt_lines")
    op.drop_index("ix_goods_receipt_lines_grn_id", table_name="goods_receipt_lines")
    op.drop_table("goods_receipt_lines")
    op.drop_index("ix_goods_receipts_location_id", table_name="goods_receipts")
    op.drop_index("ix_goods_receipts_supplier_id", table_name="goods_receipts")
    op.drop_index("ix_goods_receipts_po_id", table_name="goods_receipts")
    op.drop_index("ix_goods_receipts_grn_no", table_name="goods_receipts")
    op.drop_table("goods_receipts")
    op.drop_index("ix_purchase_order_lines_item_id", table_name="purchase_order_lines")
    op.drop_index("ix_purchase_order_lines_po_id", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
    op.drop_index("ix_purchase_orders_location_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_po_no", table_name="purchase_orders")
    op.drop_table("purchase_orders")
    op.drop_index("ix_suppliers_code", table_name="suppliers")
    op.drop_table("suppliers")
    op.drop_index("ix_inventory_counters_location_id", table_name="inventory_counters")
    op.drop_table("inventory_counters")
