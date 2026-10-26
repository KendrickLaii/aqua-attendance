"""inventory: item image

Revision ID: 048
Revises: 047
Create Date: 2026-10-27

Adds a single optional product image URL to inventory_items.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_items", "image_url")
