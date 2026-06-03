"""Product home location and allowed scan locations (whitelist).

Revision ID: 011
Revises: 010
Create Date: 2026-06-03 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_allowed_locations",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id", "location_id"),
    )
    op.create_index(
        "ix_product_allowed_locations_location_id",
        "product_allowed_locations",
        ["location_id"],
    )

    op.add_column("products", sa.Column("home_location_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_products_home_location_id",
        "products",
        "locations",
        ["home_location_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_products_home_location_id", "products", ["home_location_id"])

    conn = op.get_bind()
    default_location_id = conn.execute(
        sa.text(
            "SELECT id FROM locations WHERE is_active = true ORDER BY created_at ASC LIMIT 1"
        )
    ).scalar()

    if default_location_id is not None:
        conn.execute(
            sa.text("UPDATE products SET home_location_id = :loc_id WHERE home_location_id IS NULL"),
            {"loc_id": default_location_id},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO product_allowed_locations (product_id, location_id)
                SELECT p.id, :loc_id
                FROM products p
                WHERE NOT EXISTS (
                    SELECT 1 FROM product_allowed_locations pal WHERE pal.product_id = p.id
                )
                """
            ),
            {"loc_id": default_location_id},
        )

    null_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM products WHERE home_location_id IS NULL")
    ).scalar()
    if null_count == 0:
        op.alter_column("products", "home_location_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_products_home_location_id", table_name="products")
    op.drop_constraint("fk_products_home_location_id", "products", type_="foreignkey")
    op.drop_column("products", "home_location_id")
    op.drop_index("ix_product_allowed_locations_location_id", table_name="product_allowed_locations")
    op.drop_table("product_allowed_locations")
