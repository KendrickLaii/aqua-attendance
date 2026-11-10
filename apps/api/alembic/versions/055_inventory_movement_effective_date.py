"""inventory movement effective date

Revision ID: 055
Revises: 054
Create Date: 2026-11-10

Adds nullable ``inventory_movements.effective_date`` (NULL = same as the
``created_at`` date). Goods receipt confirmation stores the receipt date so a
back-filled GRN lands on its real date without changing ledger order. On
PostgreSQL, existing GRN ``in`` movements are backfilled from the receipt date.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_inventory_movements_effective_date"


def upgrade() -> None:
    with op.batch_alter_table("inventory_movements") as batch:
        batch.add_column(sa.Column("effective_date", sa.Date(), nullable=True))
    op.create_index(INDEX_NAME, "inventory_movements", ["effective_date"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE inventory_movements m SET effective_date = g.receipt_date "
            "FROM goods_receipts g "
            "WHERE m.type = 'in' AND m.reference LIKE 'GRN:' || g.id::text || ':%'"
        )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="inventory_movements")
    with op.batch_alter_table("inventory_movements") as batch:
        batch.drop_column("effective_date")
