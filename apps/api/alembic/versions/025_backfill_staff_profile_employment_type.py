"""Backfill empty staff_profile employment_type with full_time.

Revision ID: 025
Revises: abdfc233c749
Create Date: 2026-06-16 18:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "025"
down_revision: Union[str, None] = "abdfc233c749"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE staff_profiles
            SET employment_type = 'full_time'
            WHERE employment_type IS NULL OR employment_type = ''
            """
        )
    )


def downgrade() -> None:
    pass
