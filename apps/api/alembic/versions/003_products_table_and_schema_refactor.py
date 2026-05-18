"""Add products table, migrate attendance from user-based to product-based

Revision ID: 003
Revises: 002
Create Date: 2026-05-18 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Create products table ---
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("english_name", sa.String(255), nullable=True),
        sa.Column("product_type", sa.String(50), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("emergency_contact_name", sa.String(255), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(50), nullable=True),
        sa.Column("school_name", sa.String(255), nullable=True),
        sa.Column("grade_class", sa.String(100), nullable=True),
        sa.Column("guardian1_name", sa.String(255), nullable=True),
        sa.Column("guardian1_relationship", sa.String(100), nullable=True),
        sa.Column("guardian1_phone", sa.String(50), nullable=True),
        sa.Column("guardian2_name", sa.String(255), nullable=True),
        sa.Column("guardian2_relationship", sa.String(100), nullable=True),
        sa.Column("guardian2_phone", sa.String(50), nullable=True),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- 2. Update attendance_events: add product_id, rename scanner_user_id ---
    op.add_column(
        "attendance_events",
        sa.Column("product_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "attendance_events",
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
    )

    # Copy scanner_user_id -> recorded_by_user_id
    op.execute("UPDATE attendance_events SET recorded_by_user_id = scanner_user_id")

    # Drop old foreign keys and columns
    op.drop_constraint("attendance_events_user_id_fkey", "attendance_events", type_="foreignkey")
    op.drop_constraint("attendance_events_scanner_user_id_fkey", "attendance_events", type_="foreignkey")
    op.drop_index("ix_attendance_events_user_id", table_name="attendance_events")
    op.drop_column("attendance_events", "user_id")
    op.drop_column("attendance_events", "scanner_user_id")

    # Make product_id NOT NULL and add FK + index
    op.alter_column("attendance_events", "product_id", nullable=False)
    op.create_foreign_key(
        "attendance_events_product_id_fkey",
        "attendance_events", "products",
        ["product_id"], ["id"],
    )
    op.create_index("ix_attendance_events_product_id", "attendance_events", ["product_id"])
    op.create_foreign_key(
        "attendance_events_recorded_by_user_id_fkey",
        "attendance_events", "users",
        ["recorded_by_user_id"], ["id"],
    )

    # --- 3. Slim down users table: remove profile fields moved to products ---
    op.drop_column("users", "status")
    op.drop_column("users", "gender")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "phone")
    op.drop_column("users", "address")
    op.drop_column("users", "emergency_contact_name")
    op.drop_column("users", "emergency_contact_phone")
    op.drop_column("users", "remarks")
    op.drop_column("users", "student_code")
    op.drop_column("users", "english_name")
    op.drop_column("users", "school_name")
    op.drop_column("users", "grade_class")
    op.drop_column("users", "guardian1_name")
    op.drop_column("users", "guardian1_relationship")
    op.drop_column("users", "guardian1_phone")
    op.drop_column("users", "guardian2_name")
    op.drop_column("users", "guardian2_relationship")
    op.drop_column("users", "guardian2_phone")
    op.drop_column("users", "whatsapp_enabled")

    # Update default role from 'student' to 'admin'
    op.alter_column("users", "role", server_default="admin")


def downgrade() -> None:
    # Restore users columns
    op.alter_column("users", "role", server_default="student")
    op.add_column("users", sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("guardian2_phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("guardian2_relationship", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("guardian2_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("guardian1_phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("guardian1_relationship", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("guardian1_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("grade_class", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("school_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("english_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("student_code", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("remarks", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("emergency_contact_phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("emergency_contact_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(20), nullable=False, server_default="inactive"))

    # Restore attendance_events columns
    op.drop_constraint("attendance_events_recorded_by_user_id_fkey", "attendance_events", type_="foreignkey")
    op.drop_constraint("attendance_events_product_id_fkey", "attendance_events", type_="foreignkey")
    op.drop_index("ix_attendance_events_product_id", table_name="attendance_events")

    op.add_column("attendance_events", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column("attendance_events", sa.Column("scanner_user_id", sa.Uuid(), nullable=True))

    op.execute("UPDATE attendance_events SET scanner_user_id = recorded_by_user_id")

    op.drop_column("attendance_events", "product_id")
    op.drop_column("attendance_events", "recorded_by_user_id")

    op.create_index("ix_attendance_events_user_id", "attendance_events", ["user_id"])
    op.create_foreign_key("attendance_events_user_id_fkey", "attendance_events", "users", ["user_id"], ["id"])
    op.create_foreign_key("attendance_events_scanner_user_id_fkey", "attendance_events", "users", ["scanner_user_id"], ["id"])

    # Drop products table
    op.drop_table("products")
