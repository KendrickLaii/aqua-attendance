"""Location multi-photo URLs: icon, main, detail gallery.

Revision ID: 007
Revises: 006
Create Date: 2026-05-27 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("icon_url", sa.String(length=500), nullable=True))
    op.add_column("locations", sa.Column("main_photo_url", sa.String(length=500), nullable=True))
    op.add_column("locations", sa.Column("detail_photos", sa.JSON(), nullable=True))

    # Migrate legacy single photo_url into main_photo_url.
    op.execute(
        """
        UPDATE locations
        SET main_photo_url = photo_url
        WHERE photo_url IS NOT NULL AND photo_url <> ''
        """
    )

    op.drop_column("locations", "photo_url")


def downgrade() -> None:
    op.add_column("locations", sa.Column("photo_url", sa.String(length=500), nullable=True))
    op.execute(
        """
        UPDATE locations
        SET photo_url = main_photo_url
        WHERE main_photo_url IS NOT NULL AND main_photo_url <> ''
        """
    )
    op.drop_column("locations", "detail_photos")
    op.drop_column("locations", "main_photo_url")
    op.drop_column("locations", "icon_url")
