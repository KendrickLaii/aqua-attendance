"""staff attendance permission + recorded_by_unit_id

Revision ID: 050
Revises: 049
Create Date: 2026-10-29

Adds ``staff_profiles.can_take_attendance`` (default true, existing rows
become true) so admins can revoke mobile scanner access per staff, and
``attendance_events.recorded_by_unit_id`` so scans made by staff via the
mobile app record which staff unit performed them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "staff_profiles",
        sa.Column("can_take_attendance", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "attendance_events",
        sa.Column("recorded_by_unit_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_attendance_events_recorded_by_unit_id",
        "attendance_events",
        "units",
        ["recorded_by_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_attendance_events_recorded_by_unit_id",
        "attendance_events",
        ["recorded_by_unit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_events_recorded_by_unit_id", table_name="attendance_events")
    op.drop_constraint(
        "fk_attendance_events_recorded_by_unit_id", "attendance_events", type_="foreignkey"
    )
    op.drop_column("attendance_events", "recorded_by_unit_id")
    op.drop_column("staff_profiles", "can_take_attendance")
