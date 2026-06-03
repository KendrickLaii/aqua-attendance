"""Rename product location fields to registered + scan.

Revision ID: 012
Revises: 011
Create Date: 2026-06-03 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("product_allowed_locations", "product_scan_locations")
    op.drop_index("ix_product_allowed_locations_location_id", table_name="product_scan_locations")
    op.create_index(
        "ix_product_scan_locations_location_id",
        "product_scan_locations",
        ["location_id"],
    )

    op.drop_constraint("fk_products_home_location_id", "products", type_="foreignkey")
    op.drop_index("ix_products_home_location_id", table_name="products")
    op.alter_column("products", "home_location_id", new_column_name="registered_location_id")
    op.create_foreign_key(
        "fk_products_registered_location_id",
        "products",
        "locations",
        ["registered_location_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_products_registered_location_id", "products", ["registered_location_id"])


def downgrade() -> None:
    op.drop_index("ix_products_registered_location_id", table_name="products")
    op.drop_constraint("fk_products_registered_location_id", "products", type_="foreignkey")
    op.alter_column("products", "registered_location_id", new_column_name="home_location_id")
    op.create_foreign_key(
        "fk_products_home_location_id",
        "products",
        "locations",
        ["home_location_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_products_home_location_id", "products", ["home_location_id"])

    op.drop_index("ix_product_scan_locations_location_id", table_name="product_scan_locations")
    op.create_index(
        "ix_product_allowed_locations_location_id",
        "product_scan_locations",
        ["location_id"],
    )
    op.rename_table("product_scan_locations", "product_allowed_locations")
