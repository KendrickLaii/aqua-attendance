"""create inventory module tables

Revision ID: 042
Revises: g2a5b8c1d3e4
Create Date: 2026-10-16

- inventory_categories: item groupings (教材/文具...), soft-delete only.
- inventory_items: stockable physical items, sku_code unique.
- inventory_stocks: per-location on-hand quantity, (item_id, location_id) unique.
- inventory_movements: append-only ledger; every stock change writes one row
  with quantity_delta and balance_after. reference is unique for idempotency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "042"
down_revision: Union[str, None] = "g2a5b8c1d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name_zh", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku_code", sa.String(100), nullable=False),
        sa.Column("name_zh", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("unit_of_measure", sa.String(50), nullable=True),
        sa.Column("cost_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("sale_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_items_sku_code", "inventory_items", ["sku_code"], unique=True)
    op.create_index("ix_inventory_items_category_id", "inventory_items", ["category_id"])
    op.create_table(
        "inventory_stocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("item_id", "location_id", name="uq_inventory_stocks_item_location"),
    )
    op.create_index("ix_inventory_stocks_item_id", "inventory_stocks", ["item_id"])
    op.create_index("ix_inventory_stocks_location_id", "inventory_stocks", ["location_id"])
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_movements_item_id", "inventory_movements", ["item_id"])
    op.create_index("ix_inventory_movements_location_id", "inventory_movements", ["location_id"])
    op.create_index("ix_inventory_movements_reference", "inventory_movements", ["reference"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_reference", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_location_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_item_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_index("ix_inventory_stocks_location_id", table_name="inventory_stocks")
    op.drop_index("ix_inventory_stocks_item_id", table_name="inventory_stocks")
    op.drop_table("inventory_stocks")
    op.drop_index("ix_inventory_items_category_id", table_name="inventory_items")
    op.drop_index("ix_inventory_items_sku_code", table_name="inventory_items")
    op.drop_table("inventory_items")
    op.drop_table("inventory_categories")
