"""location attachments (private monthly images)

Revision ID: a3d5f7b9c1e2
Revises: b7c1e9a4d2f6
Create Date: 2026-10-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3d5f7b9c1e2"
down_revision: Union[str, None] = "b7c1e9a4d2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("file_key", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(255), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_location_attachments_location_id", "location_attachments", ["location_id"])
    op.create_index("ix_location_attachments_month", "location_attachments", ["month"])
    op.create_index("ix_location_attachments_loc_month", "location_attachments", ["location_id", "month"])


def downgrade() -> None:
    op.drop_index("ix_location_attachments_loc_month", table_name="location_attachments")
    op.drop_index("ix_location_attachments_month", table_name="location_attachments")
    op.drop_index("ix_location_attachments_location_id", table_name="location_attachments")
    op.drop_table("location_attachments")
