"""Add product employment_type (part_time / full_time).

Revision ID: 008
Revises: 007
Create Date: 2026-05-29 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("employment_type", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_products_employment_type", "products", ["employment_type"])


def downgrade() -> None:
    op.drop_index("ix_products_employment_type", table_name="products")
    op.drop_column("products", "employment_type")
