"""inventory: sales invoice flow rework

Revision ID: 047
Revises: 046
Create Date: 2026-10-20

New flow: SO (confirm reserves) -> Invoice issued from SO (ISSUE deducts
stock) -> Receipt. Delivery orders become sub-documents of invoices and record
physical delivery only — no stock effect.

- inventory_invoices: drop do_id.
- inventory_invoice_lines: drop do_line_id, add delivered_qty.
- sales_order_lines: drop shipped_qty, add invoiced_qty.
- delivery_orders: add invoice_id (NOT NULL, RESTRICT).
- delivery_order_lines: drop so_line_id, add invoice_line_id (NOT NULL, RESTRICT).

Both directions refuse to run while any of the four sales-document tables
hold rows — clear sales documents before migrating.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOC_TABLES = (
    "delivery_order_lines",
    "delivery_orders",
    "inventory_invoice_lines",
    "inventory_invoices",
)


def _assert_sales_docs_empty() -> None:
    conn = op.get_bind()
    for table in _DOC_TABLES:
        count = conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
        if count:
            raise RuntimeError(
                f"migration 047 requires empty sales documents: {table} has {count} row(s); "
                "clear sales documents before migrating"
            )


def upgrade() -> None:
    _assert_sales_docs_empty()

    with op.batch_alter_table("inventory_invoices", recreate="auto") as batch_op:
        batch_op.drop_index("ix_inventory_invoices_do_id")
        batch_op.drop_column("do_id")

    with op.batch_alter_table("inventory_invoice_lines", recreate="auto") as batch_op:
        batch_op.drop_index("ix_inventory_invoice_lines_do_line_id")
        batch_op.drop_column("do_line_id")
        batch_op.add_column(
            sa.Column("delivered_qty", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("sales_order_lines", recreate="auto") as batch_op:
        batch_op.drop_column("shipped_qty")
        batch_op.add_column(
            sa.Column("invoiced_qty", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("delivery_orders", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column(
                "invoice_id",
                sa.Uuid(),
                sa.ForeignKey("inventory_invoices.id", ondelete="RESTRICT", name="fk_delivery_orders_invoice_id"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_delivery_orders_invoice_id", ["invoice_id"])

    with op.batch_alter_table("delivery_order_lines", recreate="auto") as batch_op:
        batch_op.drop_index("ix_delivery_order_lines_so_line_id")
        batch_op.drop_column("so_line_id")
        batch_op.add_column(
            sa.Column(
                "invoice_line_id",
                sa.Uuid(),
                sa.ForeignKey("inventory_invoice_lines.id", ondelete="RESTRICT", name="fk_delivery_order_lines_invoice_line_id"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_delivery_order_lines_invoice_line_id", ["invoice_line_id"])


def downgrade() -> None:
    _assert_sales_docs_empty()

    with op.batch_alter_table("delivery_order_lines", recreate="auto") as batch_op:
        batch_op.drop_index("ix_delivery_order_lines_invoice_line_id")
        batch_op.drop_column("invoice_line_id")
        batch_op.add_column(
            sa.Column(
                "so_line_id",
                sa.Uuid(),
                sa.ForeignKey("sales_order_lines.id", ondelete="RESTRICT", name="fk_delivery_order_lines_so_line_id"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_delivery_order_lines_so_line_id", ["so_line_id"])

    with op.batch_alter_table("delivery_orders", recreate="auto") as batch_op:
        batch_op.drop_index("ix_delivery_orders_invoice_id")
        batch_op.drop_column("invoice_id")

    with op.batch_alter_table("sales_order_lines", recreate="auto") as batch_op:
        batch_op.drop_column("invoiced_qty")
        batch_op.add_column(
            sa.Column("shipped_qty", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("inventory_invoice_lines", recreate="auto") as batch_op:
        batch_op.drop_column("delivered_qty")
        batch_op.add_column(
            sa.Column(
                "do_line_id",
                sa.Uuid(),
                sa.ForeignKey("delivery_order_lines.id", ondelete="RESTRICT", name="fk_inventory_invoice_lines_do_line_id"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_inventory_invoice_lines_do_line_id", ["do_line_id"])

    with op.batch_alter_table("inventory_invoices", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column(
                "do_id",
                sa.Uuid(),
                sa.ForeignKey("delivery_orders.id", ondelete="RESTRICT", name="fk_inventory_invoices_do_id"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_inventory_invoices_do_id", ["do_id"])
