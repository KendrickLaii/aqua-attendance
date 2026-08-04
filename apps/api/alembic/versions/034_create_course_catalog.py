"""create course catalog (SPU/SKU) + student enrollments

Revision ID: 034
Revises: 033
Create Date: 2026-08-04

Adds a course "profile" for students, modeled the way a product catalog
usually is:

- course_spus  — the course subject/curriculum (SPU, e.g. "Primary Math")
- course_skus  — a concrete, enrollable class offering under that subject
                 (SKU, e.g. "Primary Math P3 Tue 18:00"), optionally tied to
                 a location
- course_enrollments — links a student unit to the SKU(s) they take
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_spus",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_course_spus_code", "course_spus", ["code"])
    op.create_index("ix_course_spus_subject", "course_spus", ["subject"])

    op.create_table(
        "course_skus",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("spu_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("level", sa.String(length=100), nullable=True),
        sa.Column("schedule_note", sa.String(length=255), nullable=True),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["spu_id"], ["course_spus.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_course_skus_spu_id", "course_skus", ["spu_id"])
    op.create_index("ix_course_skus_code", "course_skus", ["code"])
    op.create_index("ix_course_skus_location_id", "course_skus", ["location_id"])

    op.create_table(
        "course_enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("sku_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("enrolled_at", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["course_skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id", "sku_id", name="uq_course_enrollment_unit_sku"),
    )
    op.create_index("ix_course_enrollments_unit_id", "course_enrollments", ["unit_id"])
    op.create_index("ix_course_enrollments_sku_id", "course_enrollments", ["sku_id"])


def downgrade() -> None:
    op.drop_table("course_enrollments")
    op.drop_table("course_skus")
    op.drop_table("course_spus")
