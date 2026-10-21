"""inventory phase 2: reserved, reason_code, unit_cost, avg_cost, stocktakes

Revision ID: 043
Revises: 042
Create Date: 2026-10-16

- inventory_stocks.reserved: units reserved by sales orders (available = quantity - reserved).
- inventory_movements.reason_code + unit_cost: out-reason reporting; unit_cost
  snapshots item.avg_cost at time of issue.
- inventory_items.avg_cost: weighted average cost, updated at GRN confirm (P3).
- index (item_id, location_id, created_at) on inventory_movements.
- inventory_stocktakes + inventory_stocktake_lines: 盤點 sessions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventory_stocks",
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("reason_code", sa.String(30), nullable=True),
    )
    op.add_column(
        "inventory_movements",
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "inventory_items",
        sa.Column("avg_cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_inventory_movements_item_loc_created",
        "inventory_movements",
        ["item_id", "location_id", "created_at"],
    )
    op.create_table(
        "inventory_stocktakes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Uuid(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_inventory_stocktakes_location_id", "inventory_stocktakes", ["location_id"])
    op.create_table(
        "inventory_stocktake_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "stocktake_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_stocktakes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("system_qty", sa.Integer(), nullable=False),
        sa.Column("counted_qty", sa.Integer(), nullable=True),
        sa.UniqueConstraint("stocktake_id", "item_id", name="uq_stocktake_lines_take_item"),
    )
    op.create_index(
        "ix_inventory_stocktake_lines_stocktake_id", "inventory_stocktake_lines", ["stocktake_id"]
    )
    op.create_index("ix_inventory_stocktake_lines_item_id", "inventory_stocktake_lines", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_stocktake_lines_item_id", table_name="inventory_stocktake_lines")
    op.drop_index("ix_inventory_stocktake_lines_stocktake_id", table_name="inventory_stocktake_lines")
    op.drop_table("inventory_stocktake_lines")
    op.drop_index("ix_inventory_stocktakes_location_id", table_name="inventory_stocktakes")
    op.drop_table("inventory_stocktakes")
    op.drop_index("ix_inventory_movements_item_loc_created", table_name="inventory_movements")
    op.drop_column("inventory_items", "avg_cost")
    op.drop_column("inventory_movements", "unit_cost")
    op.drop_column("inventory_movements", "reason_code")
    op.drop_column("inventory_stocks", "reserved")
