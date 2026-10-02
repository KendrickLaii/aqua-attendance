"""one active enrollment per student per class

Drop the permanent (unit_id, sku_id) unique constraint so a student can join
the same class again after leaving. A partial unique index keeps a single
active row; cancelled and completed rows stay for invoice history.

Revision ID: a4e8c1d9b6f2
Revises: f2a6c8d0b4e1
Create Date: 2026-10-02 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4e8c1d9b6f2"
down_revision: Union[str, None] = "f2a6c8d0b4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("course_enrollments") as batch:
        batch.drop_constraint("uq_course_enrollment_unit_sku", type_="unique")
        batch.create_index(
            "uq_course_enrollment_unit_sku_active",
            ["unit_id", "sku_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )


def downgrade() -> None:
    with op.batch_alter_table("course_enrollments") as batch:
        batch.drop_index(
            "uq_course_enrollment_unit_sku_active",
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )
        batch.create_unique_constraint("uq_course_enrollment_unit_sku", ["unit_id", "sku_id"])
