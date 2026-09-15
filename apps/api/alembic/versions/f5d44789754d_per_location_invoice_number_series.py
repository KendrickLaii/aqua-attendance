"""per location invoice number series

Revision ID: f5d44789754d
Revises: 71296d8b9d7f
Create Date: 2026-09-15 17:01:45.885702

- tuition_invoices.location_id: which location this invoice belongs to.
- Backfill tuition_invoices.location_id from the student's registered location.
- Replace the global unique index on invoice_no with a per-location unique constraint.
- invoice_counters.location_id: per-location counter, so each centre has its own 1-999999 series.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5d44789754d'
down_revision: Union[str, None] = '71296d8b9d7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add location_id to tuition_invoices, backfill from the student unit.
    op.add_column(
        "tuition_invoices",
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE tuition_invoices
            SET location_id = (
                SELECT registered_location_id FROM units WHERE units.id = tuition_invoices.unit_id
            )
            """
        )
    )
    # Manual/walk-in invoices have no unit; assign them to the first available location
    # rather than leaving a non-nullable location_id as NULL.
    op.execute(
        sa.text(
            """
            UPDATE tuition_invoices
            SET location_id = (SELECT id FROM locations ORDER BY name_en LIMIT 1)
            WHERE location_id IS NULL
            """
        )
    )
    op.alter_column("tuition_invoices", "location_id", nullable=False)
    op.create_index("ix_tuition_invoices_location_id", "tuition_invoices", ["location_id"])

    # 2. Replace global unique on invoice_no with per-location unique.
    op.drop_index("ix_tuition_invoices_invoice_no", table_name="tuition_invoices")
    op.create_unique_constraint(
        "uq_tuition_invoices_location_invoice_no",
        "tuition_invoices",
        ["location_id", "invoice_no"],
    )

    # 3. Add location_id to invoice_counters and make it the unique key for a series.
    op.add_column(
        "invoice_counters",
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_invoice_counters_location_id", "invoice_counters", ["location_id"], unique=True)

    # 4. Seed per-location counters from the highest numeric invoice_no at each location.
    bind = op.get_bind()
    locations = list(
        bind.execute(
            sa.text("SELECT DISTINCT location_id FROM tuition_invoices WHERE location_id IS NOT NULL")
        ).scalars()
    )
    max_id = bind.execute(sa.text("SELECT COALESCE(MAX(id), 0) FROM invoice_counters")).scalar() or 0
    for i, loc_id in enumerate(locations, start=1):
        rows = bind.execute(
            sa.text(
                "SELECT invoice_no FROM tuition_invoices "
                "WHERE location_id = :loc AND invoice_no IS NOT NULL"
            ),
            {"loc": loc_id},
        ).scalars()
        max_no = max((int(v) for v in rows if str(v).strip().isdigit()), default=0)
        bind.execute(
            sa.text("INSERT INTO invoice_counters (id, location_id, next_no) VALUES (:id, :loc, :n)"),
            {"id": max_id + i, "loc": loc_id, "n": max_no + 1},
        )


def downgrade() -> None:
    op.drop_index("ix_invoice_counters_location_id", table_name="invoice_counters")
    op.drop_column("invoice_counters", "location_id")
    op.drop_constraint("uq_tuition_invoices_location_invoice_no", table_name="tuition_invoices")
    op.create_index(
        "ix_tuition_invoices_invoice_no",
        "tuition_invoices",
        ["invoice_no"],
        unique=True,
    )
    op.drop_index("ix_tuition_invoices_location_id", table_name="tuition_invoices")
    op.drop_column("tuition_invoices", "location_id")
