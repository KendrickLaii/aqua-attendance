"""Add locations table and location foreign keys.

Revision ID: 006
Revises: 005
Create Date: 2026-05-27 17:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("location_type", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("business_hours", sa.String(length=255), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("contact_person", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_locations_code"), "locations", ["code"], unique=False)
    op.create_index(op.f("ix_locations_location_type"), "locations", ["location_type"], unique=False)
    op.create_index(op.f("ix_locations_region"), "locations", ["region"], unique=False)

    op.add_column("attendance_events", sa.Column("location_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_attendance_events_location_id"), "attendance_events", ["location_id"], unique=False)
    op.create_foreign_key(
        "fk_attendance_events_location_id_locations",
        "attendance_events",
        "locations",
        ["location_id"],
        ["id"],
    )

    op.add_column("products", sa.Column("last_event_location_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_products_last_event_location_id"), "products", ["last_event_location_id"], unique=False)
    op.create_foreign_key(
        "fk_products_last_event_location_id_locations",
        "products",
        "locations",
        ["last_event_location_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_last_event_location_id_locations", "products", type_="foreignkey")
    op.drop_index(op.f("ix_products_last_event_location_id"), table_name="products")
    op.drop_column("products", "last_event_location_id")

    op.drop_constraint("fk_attendance_events_location_id_locations", "attendance_events", type_="foreignkey")
    op.drop_index(op.f("ix_attendance_events_location_id"), table_name="attendance_events")
    op.drop_column("attendance_events", "location_id")

    op.drop_index(op.f("ix_locations_region"), table_name="locations")
    op.drop_index(op.f("ix_locations_location_type"), table_name="locations")
    op.drop_index(op.f("ix_locations_code"), table_name="locations")
    op.drop_table("locations")
