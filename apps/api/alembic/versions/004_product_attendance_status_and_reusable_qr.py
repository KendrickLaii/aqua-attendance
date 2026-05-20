"""Add product attendance_status and qr_token_version; relax qr_jti unique

Revision ID: 004
Revises: 003
Create Date: 2026-05-20 13:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "attendance_status",
            sa.String(20),
            nullable=False,
            server_default="checked_out",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "qr_token_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "last_event_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # The QR token is now reusable per product, so jti is no longer globally
    # unique across scans. Drop the unique constraint but keep the index for
    # fast lookups when debouncing or auditing.
    with op.batch_alter_table("attendance_events") as batch:
        batch.drop_index("ix_attendance_events_qr_jti")
    op.create_index(
        "ix_attendance_events_qr_jti",
        "attendance_events",
        ["qr_jti"],
        unique=False,
    )

    # Backfill attendance_status and last_event_at from the latest event per product.
    # Only treat events recorded today (UTC) as "still checked in"; older
    # events leave the product as the default checked_out.
    op.execute(
        """
        UPDATE products p
        SET
            attendance_status = CASE
                WHEN latest.event_type = 'check_in'
                     AND latest.recorded_at >= (CURRENT_DATE AT TIME ZONE 'UTC')
                THEN 'checked_in'
                ELSE 'checked_out'
            END,
            last_event_at = latest.recorded_at
        FROM (
            SELECT DISTINCT ON (product_id)
                product_id, event_type, recorded_at
            FROM attendance_events
            WHERE event_type IN ('check_in', 'check_out')
            ORDER BY product_id, recorded_at DESC
        ) latest
        WHERE p.id = latest.product_id
        """
    )


def downgrade() -> None:
    op.drop_column("products", "last_event_at")
    op.drop_column("products", "qr_token_version")
    op.drop_column("products", "attendance_status")

    with op.batch_alter_table("attendance_events") as batch:
        batch.drop_index("ix_attendance_events_qr_jti")
    op.create_index(
        "ix_attendance_events_qr_jti",
        "attendance_events",
        ["qr_jti"],
        unique=True,
    )
