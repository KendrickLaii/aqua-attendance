"""Expand users profile fields

Revision ID: 002
Revises: 001
Create Date: 2026-05-06 16:56:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("status", sa.String(length=20), nullable=False, server_default="inactive"))
    op.add_column("users", sa.Column("gender", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("emergency_contact_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("emergency_contact_phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("remarks", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("student_code", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("english_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("school_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("grade_class", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("guardian1_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("guardian1_relationship", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("guardian1_phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("guardian2_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("guardian2_relationship", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("guardian2_phone", sa.String(length=50), nullable=True))
    op.add_column(
        "users",
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("users", "whatsapp_enabled")
    op.drop_column("users", "guardian2_phone")
    op.drop_column("users", "guardian2_relationship")
    op.drop_column("users", "guardian2_name")
    op.drop_column("users", "guardian1_phone")
    op.drop_column("users", "guardian1_relationship")
    op.drop_column("users", "guardian1_name")
    op.drop_column("users", "grade_class")
    op.drop_column("users", "school_name")
    op.drop_column("users", "english_name")
    op.drop_column("users", "student_code")
    op.drop_column("users", "remarks")
    op.drop_column("users", "emergency_contact_phone")
    op.drop_column("users", "emergency_contact_name")
    op.drop_column("users", "address")
    op.drop_column("users", "phone")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "gender")
    op.drop_column("users", "status")
