"""inventory: item sub images

Revision ID: 049
Revises: 048
Create Date: 2026-10-27

Adds an optional JSON list of up to two sub-image URLs to inventory_items.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("sub_image_urls", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_items", "sub_image_urls")
