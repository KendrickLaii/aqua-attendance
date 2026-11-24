"""shared invoice job names

Revision ID: 057
Revises: 056
Create Date: 2026-11-23

CPA invoice lines pick a job from this list. Seeded with the names already
in use. Users can add and delete rows afterwards.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_JOBS = (
    "AT",
    "Discount",
    "Non recurring",
    "OT",
    "OT - 6 months",
    "OT - Monthly",
    "OT - Odd",
    "OT - Quarterly",
    "PB",
    "Recurring",
)


def upgrade() -> None:
    op.create_table(
        "invoice_job_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    job_table = sa.table(
        "invoice_job_options",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
    )
    op.bulk_insert(
        job_table,
        [{"id": uuid.uuid4(), "name": name} for name in SEED_JOBS],
    )


def downgrade() -> None:
    op.drop_table("invoice_job_options")
