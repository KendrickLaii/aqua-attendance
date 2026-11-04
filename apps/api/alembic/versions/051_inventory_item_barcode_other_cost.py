"""inventory item barcode + other_cost

Revision ID: 051
Revises: 050
Create Date: 2026-11-04

Adds ``inventory_items.barcode`` (nullable, indexed, not unique) for
scan-based item lookup, and ``inventory_items.other_cost`` (nullable
Numeric(10,2)) for extra per-item costs beyond the purchase price.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventory_items",
        sa.Column("barcode", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_inventory_items_barcode", "inventory_items", ["barcode"])
    op.add_column(
        "inventory_items",
        sa.Column("other_cost", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "other_cost")
    op.drop_index("ix_inventory_items_barcode", table_name="inventory_items")
    op.drop_column("inventory_items", "barcode")
