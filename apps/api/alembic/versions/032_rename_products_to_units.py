"""Rename products table and product_id columns to units / unit_id.

Revision ID: 032
Revises: 031
Create Date: 2026-07-18

Renames the ``products`` table to ``units`` and all ``product_id`` foreign
key columns to ``unit_id`` across attendance_events, attendance_summaries,
notifications, payroll_records, student_profiles, staff_profiles, and the
association table product_scan_locations → unit_scan_locations.

Also renames related indexes, constraints, and the product_type column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- attendance_events: rename product_id → unit_id ---
    op.drop_constraint("attendance_events_product_id_fkey", "attendance_events", type_="foreignkey")
    op.drop_index("ix_attendance_events_product_id", table_name="attendance_events")
    op.alter_column("attendance_events", "product_id", new_column_name="unit_id")
    op.create_foreign_key(
        "attendance_events_unit_id_fkey",
        "attendance_events", "products",
        ["unit_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_attendance_events_unit_id", "attendance_events", ["unit_id"])

    # --- attendance_summaries: rename product_id → unit_id ---
    op.drop_constraint(
        op.f("attendance_summaries_product_id_fkey"),
        "attendance_summaries",
        type_="foreignkey",
    )
    op.drop_index("ix_attendance_summaries_product_id", table_name="attendance_summaries")
    op.drop_constraint("uq_attendance_summaries_product_date", "attendance_summaries", type_="unique")
    op.alter_column("attendance_summaries", "product_id", new_column_name="unit_id")
    op.create_foreign_key(
        "attendance_summaries_unit_id_fkey",
        "attendance_summaries", "products",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_attendance_summaries_unit_id", "attendance_summaries", ["unit_id"])
    op.create_unique_constraint(
        "uq_attendance_summaries_unit_date",
        "attendance_summaries",
        ["unit_id", "summary_date"],
    )

    # --- notifications: rename product_id → unit_id ---
    op.drop_constraint(
        op.f("notifications_product_id_fkey"),
        "notifications",
        type_="foreignkey",
    )
    op.drop_index("ix_notifications_product_id", table_name="notifications")
    op.alter_column("notifications", "product_id", new_column_name="unit_id")
    op.create_foreign_key(
        "notifications_unit_id_fkey",
        "notifications", "products",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notifications_unit_id", "notifications", ["unit_id"])

    # --- payroll_records: rename product_id → unit_id ---
    op.drop_constraint(
        op.f("payroll_records_product_id_fkey"),
        "payroll_records",
        type_="foreignkey",
    )
    op.drop_index("ix_payroll_records_product_id", table_name="payroll_records")
    op.drop_constraint("uq_payroll_records_product_period", "payroll_records", type_="unique")
    op.alter_column("payroll_records", "product_id", new_column_name="unit_id")
    op.create_foreign_key(
        "payroll_records_unit_id_fkey",
        "payroll_records", "products",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_payroll_records_unit_id", "payroll_records", ["unit_id"])
    op.create_unique_constraint(
        "uq_payroll_records_unit_period",
        "payroll_records",
        ["unit_id", "payroll_period_start", "payroll_period_end"],
    )

    # --- student_profiles: FK already references products.id via id column ---
    # The id column IS the FK to products.id, so no column rename needed.
    # But the FK constraint name may reference "products" — drop and recreate.
    op.drop_constraint("student_profiles_id_fkey", "student_profiles", type_="foreignkey")
    op.create_foreign_key(
        "student_profiles_id_fkey",
        "student_profiles", "products",
        ["id"], ["id"],
        ondelete="CASCADE",
    )

    # --- staff_profiles: FK on id and supervisor_id ---
    op.drop_constraint("staff_profiles_id_fkey", "staff_profiles", type_="foreignkey")
    op.drop_constraint("staff_profiles_supervisor_id_fkey", "staff_profiles", type_="foreignkey")
    op.create_foreign_key(
        "staff_profiles_id_fkey",
        "staff_profiles", "products",
        ["id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "staff_profiles_supervisor_id_fkey",
        "staff_profiles", "products",
        ["supervisor_id"], ["id"],
    )

    # --- product_scan_locations → unit_scan_locations ---
    op.drop_index("ix_product_scan_locations_location_id", table_name="product_scan_locations")
    op.drop_constraint(
        "product_scan_locations_product_id_fkey",
        "product_scan_locations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "product_scan_locations_location_id_fkey",
        "product_scan_locations",
        type_="foreignkey",
    )
    op.rename_table("product_scan_locations", "unit_scan_locations")
    op.alter_column("unit_scan_locations", "product_id", new_column_name="unit_id")
    op.create_foreign_key(
        "unit_scan_locations_unit_id_fkey",
        "unit_scan_locations", "products",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "unit_scan_locations_location_id_fkey",
        "unit_scan_locations", "locations",
        ["location_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_unit_scan_locations_location_id", "unit_scan_locations", ["location_id"])

    # --- products table: rename product_type → unit_type, then rename table ---
    op.drop_index("ix_products_product_type", table_name="products")
    op.alter_column("products", "product_type", new_column_name="unit_type")
    op.create_index("ix_units_unit_type", "products", ["unit_type"])

    # Rename remaining product indexes/constraints on the products table
    op.drop_index("ix_products_registered_location_id", table_name="products")
    op.drop_constraint("fk_products_registered_location_id", "products", type_="foreignkey")
    op.drop_index("ix_products_last_event_location_id", table_name="products")
    op.drop_constraint("fk_products_last_event_location_id_locations", "products", type_="foreignkey")

    op.rename_table("products", "units")

    op.create_foreign_key(
        "fk_units_registered_location_id",
        "units", "locations",
        ["registered_location_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_units_registered_location_id", "units", ["registered_location_id"])
    op.create_foreign_key(
        "fk_units_last_event_location_id_locations",
        "units", "locations",
        ["last_event_location_id"], ["id"],
    )
    op.create_index("ix_units_last_event_location_id", "units", ["last_event_location_id"])

    # --- Fix FK references to point to 'units' table instead of 'products' ---
    op.drop_constraint("attendance_events_unit_id_fkey", "attendance_events", type_="foreignkey")
    op.create_foreign_key(
        "attendance_events_unit_id_fkey",
        "attendance_events", "units",
        ["unit_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("attendance_summaries_unit_id_fkey", "attendance_summaries", type_="foreignkey")
    op.create_foreign_key(
        "attendance_summaries_unit_id_fkey",
        "attendance_summaries", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("notifications_unit_id_fkey", "notifications", type_="foreignkey")
    op.create_foreign_key(
        "notifications_unit_id_fkey",
        "notifications", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("payroll_records_unit_id_fkey", "payroll_records", type_="foreignkey")
    op.create_foreign_key(
        "payroll_records_unit_id_fkey",
        "payroll_records", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("student_profiles_id_fkey", "student_profiles", type_="foreignkey")
    op.create_foreign_key(
        "student_profiles_id_fkey",
        "student_profiles", "units",
        ["id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("staff_profiles_id_fkey", "staff_profiles", type_="foreignkey")
    op.drop_constraint("staff_profiles_supervisor_id_fkey", "staff_profiles", type_="foreignkey")
    op.create_foreign_key(
        "staff_profiles_id_fkey",
        "staff_profiles", "units",
        ["id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "staff_profiles_supervisor_id_fkey",
        "staff_profiles", "units",
        ["supervisor_id"], ["id"],
    )
    op.drop_constraint("unit_scan_locations_unit_id_fkey", "unit_scan_locations", type_="foreignkey")
    op.create_foreign_key(
        "unit_scan_locations_unit_id_fkey",
        "unit_scan_locations", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Reverse all FK references back to 'products' table
    op.drop_constraint("unit_scan_locations_unit_id_fkey", "unit_scan_locations", type_="foreignkey")
    op.create_foreign_key(
        "unit_scan_locations_unit_id_fkey",
        "unit_scan_locations", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("staff_profiles_supervisor_id_fkey", "staff_profiles", type_="foreignkey")
    op.drop_constraint("staff_profiles_id_fkey", "staff_profiles", type_="foreignkey")
    op.create_foreign_key(
        "staff_profiles_id_fkey",
        "staff_profiles", "units",
        ["id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "staff_profiles_supervisor_id_fkey",
        "staff_profiles", "units",
        ["supervisor_id"], ["id"],
    )
    op.drop_constraint("student_profiles_id_fkey", "student_profiles", type_="foreignkey")
    op.create_foreign_key(
        "student_profiles_id_fkey",
        "student_profiles", "units",
        ["id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("payroll_records_unit_id_fkey", "payroll_records", type_="foreignkey")
    op.create_foreign_key(
        "payroll_records_unit_id_fkey",
        "payroll_records", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("notifications_unit_id_fkey", "notifications", type_="foreignkey")
    op.create_foreign_key(
        "notifications_unit_id_fkey",
        "notifications", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("attendance_summaries_unit_id_fkey", "attendance_summaries", type_="foreignkey")
    op.create_foreign_key(
        "attendance_summaries_unit_id_fkey",
        "attendance_summaries", "units",
        ["unit_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("attendance_events_unit_id_fkey", "attendance_events", type_="foreignkey")
    op.create_foreign_key(
        "attendance_events_unit_id_fkey",
        "attendance_events", "units",
        ["unit_id"], ["id"],
        ondelete="RESTRICT",
    )

    # Rename units table back to products
    op.drop_index("ix_units_last_event_location_id", table_name="units")
    op.drop_constraint("fk_units_last_event_location_id_locations", "units", type_="foreignkey")
    op.drop_index("ix_units_registered_location_id", table_name="units")
    op.drop_constraint("fk_units_registered_location_id", "units", type_="foreignkey")
    op.rename_table("units", "products")
    op.create_foreign_key(
        "fk_products_registered_location_id",
        "products", "locations",
        ["registered_location_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_products_registered_location_id", "products", ["registered_location_id"])
    op.create_foreign_key(
        "fk_products_last_event_location_id_locations",
        "products", "locations",
        ["last_event_location_id"], ["id"],
    )
    op.create_index("ix_products_last_event_location_id", "products", ["last_event_location_id"])

    # Rename unit_type back to product_type
    op.drop_index("ix_units_unit_type", table_name="products")
    op.alter_column("products", "unit_type", new_column_name="product_type")
    op.create_index("ix_products_product_type", "products", ["product_type"])

    # Reverse unit_scan_locations → product_scan_locations
    op.drop_index("ix_unit_scan_locations_location_id", table_name="unit_scan_locations")
    op.drop_constraint("unit_scan_locations_location_id_fkey", "unit_scan_locations", type_="foreignkey")
    op.drop_constraint("unit_scan_locations_unit_id_fkey", "unit_scan_locations", type_="foreignkey")
    op.alter_column("unit_scan_locations", "unit_id", new_column_name="product_id")
    op.rename_table("unit_scan_locations", "product_scan_locations")
    op.create_foreign_key(
        "product_scan_locations_product_id_fkey",
        "product_scan_locations", "products",
        ["product_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "product_scan_locations_location_id_fkey",
        "product_scan_locations", "locations",
        ["location_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_product_scan_locations_location_id", "product_scan_locations", ["location_id"])

    # Reverse staff_profiles FKs
    op.drop_constraint("staff_profiles_supervisor_id_fkey", "staff_profiles", type_="foreignkey")
    op.drop_constraint("staff_profiles_id_fkey", "staff_profiles", type_="foreignkey")
    op.create_foreign_key(
        "staff_profiles_id_fkey",
        "staff_profiles", "products",
        ["id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "staff_profiles_supervisor_id_fkey",
        "staff_profiles", "products",
        ["supervisor_id"], ["id"],
    )

    # Reverse student_profiles FK
    op.drop_constraint("student_profiles_id_fkey", "student_profiles", type_="foreignkey")
    op.create_foreign_key(
        "student_profiles_id_fkey",
        "student_profiles", "products",
        ["id"], ["id"],
        ondelete="CASCADE",
    )

    # Reverse payroll_records
    op.drop_constraint("uq_payroll_records_unit_period", "payroll_records", type_="unique")
    op.drop_index("ix_payroll_records_unit_id", table_name="payroll_records")
    op.drop_constraint("payroll_records_unit_id_fkey", "payroll_records", type_="foreignkey")
    op.alter_column("payroll_records", "unit_id", new_column_name="product_id")
    op.create_foreign_key(
        "payroll_records_product_id_fkey",
        "payroll_records", "products",
        ["product_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_payroll_records_product_id", "payroll_records", ["product_id"])
    op.create_unique_constraint(
        "uq_payroll_records_product_period",
        "payroll_records",
        ["product_id", "payroll_period_start", "payroll_period_end"],
    )

    # Reverse notifications
    op.drop_index("ix_notifications_unit_id", table_name="notifications")
    op.drop_constraint("notifications_unit_id_fkey", "notifications", type_="foreignkey")
    op.alter_column("notifications", "unit_id", new_column_name="product_id")
    op.create_foreign_key(
        "notifications_product_id_fkey",
        "notifications", "products",
        ["product_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notifications_product_id", "notifications", ["product_id"])

    # Reverse attendance_summaries
    op.drop_constraint("uq_attendance_summaries_unit_date", "attendance_summaries", type_="unique")
    op.drop_index("ix_attendance_summaries_unit_id", table_name="attendance_summaries")
    op.drop_constraint("attendance_summaries_unit_id_fkey", "attendance_summaries", type_="foreignkey")
    op.alter_column("attendance_summaries", "unit_id", new_column_name="product_id")
    op.create_foreign_key(
        "attendance_summaries_product_id_fkey",
        "attendance_summaries", "products",
        ["product_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_attendance_summaries_product_id", "attendance_summaries", ["product_id"])
    op.create_unique_constraint(
        "uq_attendance_summaries_product_date",
        "attendance_summaries",
        ["product_id", "summary_date"],
    )

    # Reverse attendance_events
    op.drop_index("ix_attendance_events_unit_id", table_name="attendance_events")
    op.drop_constraint("attendance_events_unit_id_fkey", "attendance_events", type_="foreignkey")
    op.alter_column("attendance_events", "unit_id", new_column_name="product_id")
    op.create_foreign_key(
        "attendance_events_product_id_fkey",
        "attendance_events", "products",
        ["product_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_attendance_events_product_id", "attendance_events", ["product_id"])
