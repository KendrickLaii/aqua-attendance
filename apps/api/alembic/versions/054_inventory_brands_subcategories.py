"""inventory brands and two-level categories

Revision ID: 054
Revises: 053
Create Date: 2026-11-10

Adds ``inventory_brands``, ``inventory_categories.parent_id`` (self FK, two
levels enforced in the API) and nullable ``brand_id`` on ``inventory_products``
and ``inventory_items``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BRAND_FK = "fk_{table}_brand_id_inventory_brands"


def upgrade() -> None:
    op.create_table(
        "inventory_brands",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("inventory_categories") as batch:
        batch.add_column(sa.Column("parent_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_inventory_categories_parent_id_inventory_categories",
            "inventory_categories",
            ["parent_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index("ix_inventory_categories_parent_id", ["parent_id"])

    for table in ("inventory_products", "inventory_items"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("brand_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key(
                BRAND_FK.format(table=table), "inventory_brands", ["brand_id"], ["id"], ondelete="RESTRICT"
            )
            batch.create_index(f"ix_{table}_brand_id", ["brand_id"])


def downgrade() -> None:
    for table in ("inventory_items", "inventory_products"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_brand_id")
            batch.drop_constraint(BRAND_FK.format(table=table), type_="foreignkey")
            batch.drop_column("brand_id")

    with op.batch_alter_table("inventory_categories") as batch:
        batch.drop_index("ix_inventory_categories_parent_id")
        batch.drop_constraint("fk_inventory_categories_parent_id_inventory_categories", type_="foreignkey")
        batch.drop_column("parent_id")

    op.drop_table("inventory_brands")
