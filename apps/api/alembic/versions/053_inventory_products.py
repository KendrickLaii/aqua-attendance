"""inventory products (SPU) above SKUs

Revision ID: 053
Revises: 052
Create Date: 2026-11-10

Adds ``inventory_products`` (SPU) and links ``inventory_items`` (SKU) to it via
nullable ``product_id`` plus a ``variant_attrs`` JSON column. SKUs stay real
rows so stocks, movements and documents keep pointing at ``inventory_items``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey("inventory_categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("unit_of_measure", sa.String(length=50), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventory_products_code", "inventory_products", ["code"], unique=True)
    op.create_index("ix_inventory_products_category_id", "inventory_products", ["category_id"])

    with op.batch_alter_table("inventory_items") as batch:
        batch.add_column(sa.Column("product_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("variant_attrs", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_inventory_items_product_id_inventory_products",
            "inventory_products",
            ["product_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_inventory_items_product_id", ["product_id"])


def downgrade() -> None:
    with op.batch_alter_table("inventory_items") as batch:
        batch.drop_index("ix_inventory_items_product_id")
        batch.drop_constraint("fk_inventory_items_product_id_inventory_products", type_="foreignkey")
        batch.drop_column("variant_attrs")
        batch.drop_column("product_id")

    op.drop_index("ix_inventory_products_category_id", table_name="inventory_products")
    op.drop_index("ix_inventory_products_code", table_name="inventory_products")
    op.drop_table("inventory_products")
