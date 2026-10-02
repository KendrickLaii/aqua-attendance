"""staff shift PIN and shift requests

Revision ID: b7c1e9a4d2f6
Revises: a4e8c1d9b6f2
Create Date: 2026-10-02 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c1e9a4d2f6"
down_revision: Union[str, None] = "a4e8c1d9b6f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("staff_profiles", sa.Column("shift_pin_hash", sa.String(255), nullable=True))
    op.add_column("staff_profiles", sa.Column("shift_pin_set_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "shift_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reject_reason", sa.String(500), nullable=True),
        sa.Column("shift_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["shift_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_shift_requests_unit_id", "shift_requests", ["unit_id"])
    op.create_index("ix_shift_requests_location_id", "shift_requests", ["location_id"])
    op.create_index("ix_shift_requests_shift_date", "shift_requests", ["shift_date"])
    op.create_index("ix_shift_requests_status", "shift_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_shift_requests_status", table_name="shift_requests")
    op.drop_index("ix_shift_requests_shift_date", table_name="shift_requests")
    op.drop_index("ix_shift_requests_location_id", table_name="shift_requests")
    op.drop_index("ix_shift_requests_unit_id", table_name="shift_requests")
    op.drop_table("shift_requests")
    op.drop_column("staff_profiles", "shift_pin_set_at")
    op.drop_column("staff_profiles", "shift_pin_hash")
