"""let each team keep the original line item code

Revision ID: 060
Revises: 059
Create Date: 2026-11-24

Migration 058 copied line items that had no team onto every team and appended
the team id so the old global code unique constraint still held. Codes are now
unique per team, and those suffixes are removed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("course_skus_code_key", "course_skus", type_="unique")
    op.execute(
        sa.text(
            """
            UPDATE course_skus
            SET code = left(code, length(code) - 7)
            WHERE code ~ ('-' || left(replace(location_id::text, '-', ''), 6) || '$')
            """
        )
    )
    op.create_unique_constraint(
        "uq_course_skus_location_code", "course_skus", ["location_id", "code"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_course_skus_location_code", "course_skus", type_="unique")
    op.execute(
        sa.text(
            """
            UPDATE course_skus AS sku
            SET code = sku.code || '-' || left(replace(sku.location_id::text, '-', ''), 6)
            WHERE EXISTS (
                SELECT 1 FROM course_skus AS other
                WHERE other.code = sku.code AND other.id <> sku.id
            )
            """
        )
    )
    op.create_unique_constraint("course_skus_code_key", "course_skus", ["code"])
