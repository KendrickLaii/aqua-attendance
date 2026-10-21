"""inventory phase 4: customers, sales orders, proforma, delivery orders

Revision ID: 045
Revises: 044
Create Date: 2026-10-16

- customers (optional link back to a student unit).
- sales_orders + sales_order_lines (frozen sku/name, line + header discounts,
  proforma fields pf_no / pf_issued_at / pf_valid_until).
- delivery_orders + delivery_order_lines (confirm releases the reservation and
  writes the out movement; void reverses).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name_zh", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("type", sa.String(20), nullable=False, server_default="individual"),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column(
            "student_unit_id",
            sa.Uuid(),
            sa.ForeignKey("units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customers_code", "customers", ["code"], unique=True)
    op.create_index("ix_customers_student_unit_id", "customers", ["student_unit_id"], unique=True)

    op.create_table(
        "sales_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("so_no", sa.String(50), nullable=False),
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
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("pf_no", sa.String(50), nullable=True),
        sa.Column("pf_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pf_valid_until", sa.Date(), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sales_orders_so_no", "sales_orders", ["so_no"], unique=True)
    op.create_index("ix_sales_orders_pf_no", "sales_orders", ["pf_no"], unique=True)
    op.create_index("ix_sales_orders_customer_id", "sales_orders", ["customer_id"])
    op.create_index("ix_sales_orders_location_id", "sales_orders", ["location_id"])

    op.create_table(
        "sales_order_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "so_id",
            sa.Uuid(),
            sa.ForeignKey("sales_orders.id", ondelete="CASCADE"),
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
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("shipped_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_sales_order_lines_so_id", "sales_order_lines", ["so_id"])
    op.create_index("ix_sales_order_lines_item_id", "sales_order_lines", ["item_id"])

    op.create_table(
        "delivery_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("do_no", sa.String(50), nullable=False),
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
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
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
    op.create_index("ix_delivery_orders_do_no", "delivery_orders", ["do_no"], unique=True)
    op.create_index("ix_delivery_orders_so_id", "delivery_orders", ["so_id"])
    op.create_index("ix_delivery_orders_customer_id", "delivery_orders", ["customer_id"])
    op.create_index("ix_delivery_orders_location_id", "delivery_orders", ["location_id"])

    op.create_table(
        "delivery_order_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "do_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_orders.id", ondelete="CASCADE"),
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
        sa.Column("qty", sa.Integer(), nullable=False),
    )
    op.create_index("ix_delivery_order_lines_do_id", "delivery_order_lines", ["do_id"])
    op.create_index("ix_delivery_order_lines_so_line_id", "delivery_order_lines", ["so_line_id"])
    op.create_index("ix_delivery_order_lines_item_id", "delivery_order_lines", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_order_lines_item_id", table_name="delivery_order_lines")
    op.drop_index("ix_delivery_order_lines_so_line_id", table_name="delivery_order_lines")
    op.drop_index("ix_delivery_order_lines_do_id", table_name="delivery_order_lines")
    op.drop_table("delivery_order_lines")
    op.drop_index("ix_delivery_orders_location_id", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_customer_id", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_so_id", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_do_no", table_name="delivery_orders")
    op.drop_table("delivery_orders")
    op.drop_index("ix_sales_order_lines_item_id", table_name="sales_order_lines")
    op.drop_index("ix_sales_order_lines_so_id", table_name="sales_order_lines")
    op.drop_table("sales_order_lines")
    op.drop_index("ix_sales_orders_location_id", table_name="sales_orders")
    op.drop_index("ix_sales_orders_customer_id", table_name="sales_orders")
    op.drop_index("ix_sales_orders_pf_no", table_name="sales_orders")
    op.drop_index("ix_sales_orders_so_no", table_name="sales_orders")
    op.drop_table("sales_orders")
    op.drop_index("ix_customers_student_unit_id", table_name="customers")
    op.drop_index("ix_customers_code", table_name="customers")
    op.drop_table("customers")
