"""Require locations.name_en (English name is mandatory in the app).

Revision ID: 010
Revises: 009
Create Date: 2026-06-03 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill any legacy NULL rows (should be none in a fresh deploy).
    op.execute(
        sa.text(
            "UPDATE locations SET name_en = name_zh "
            "WHERE name_en IS NULL AND name_zh IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE locations SET name_en = '' "
            "WHERE name_en IS NULL"
        )
    )
    op.alter_column("locations", "name_en", existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    op.alter_column("locations", "name_en", existing_type=sa.String(length=255), nullable=True)
