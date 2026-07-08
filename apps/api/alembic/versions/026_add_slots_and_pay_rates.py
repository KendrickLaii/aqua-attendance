"""Add slots and pay rates for slot-based payroll system.

Revision ID: 026
Revises: 025
Create Date: 2026-07-08 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add slot-based source of truth to daily attendance summaries
    op.add_column(
        "attendance_summaries",
        sa.Column("regular_slots", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "attendance_summaries",
        sa.Column("ot_slots", sa.Integer(), nullable=False, server_default="0"),
    )

    # Add pay-rate fields to staff profiles
    op.add_column(
        "staff_profiles",
        sa.Column("pay_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "staff_profiles",
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "staff_profiles",
        sa.Column("monthly_salary", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "staff_profiles",
        sa.Column("ot_multiplier", sa.Numeric(precision=4, scale=2), server_default="1.5", nullable=True),
    )

    # Add slot snapshots and rate snapshots to payroll records
    op.add_column(
        "payroll_records",
        sa.Column("regular_slots", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payroll_records",
        sa.Column("ot_slots", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payroll_records",
        sa.Column("hourly_rate_snapshot", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "payroll_records",
        sa.Column("ot_multiplier_snapshot", sa.Numeric(precision=4, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payroll_records", "ot_multiplier_snapshot")
    op.drop_column("payroll_records", "hourly_rate_snapshot")
    op.drop_column("payroll_records", "ot_slots")
    op.drop_column("payroll_records", "regular_slots")

    op.drop_column("staff_profiles", "ot_multiplier")
    op.drop_column("staff_profiles", "monthly_salary")
    op.drop_column("staff_profiles", "hourly_rate")
    op.drop_column("staff_profiles", "pay_type")

    op.drop_column("attendance_summaries", "ot_slots")
    op.drop_column("attendance_summaries", "regular_slots")
