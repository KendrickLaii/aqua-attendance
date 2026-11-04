"""inventory warehouses (decoupled from attendance locations)

Revision ID: 052
Revises: 051
Create Date: 2026-11-04

Adds ``inventory_warehouses`` and repoints every inventory table from
``locations.id`` to ``inventory_warehouses.id``. Each location that is
referenced by inventory data becomes a warehouse that REUSES the location id
(code/name/address/phone copied), so no row data changes and document
numbering continues.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, old column, new column, ondelete, has single-col index named ix_<table>_<old>)
COLUMNS = [
    ("inventory_stocks", "location_id", "warehouse_id", "RESTRICT"),
    ("inventory_movements", "location_id", "warehouse_id", "RESTRICT"),
    ("inventory_stocktakes", "location_id", "warehouse_id", "RESTRICT"),
    ("inventory_counters", "location_id", "warehouse_id", "CASCADE"),
    ("purchase_orders", "location_id", "warehouse_id", "RESTRICT"),
    ("goods_receipts", "location_id", "warehouse_id", "RESTRICT"),
    ("purchase_returns", "location_id", "warehouse_id", "RESTRICT"),
    ("sales_orders", "location_id", "warehouse_id", "RESTRICT"),
    ("delivery_orders", "location_id", "warehouse_id", "RESTRICT"),
    ("inventory_invoices", "location_id", "warehouse_id", "RESTRICT"),
    ("inventory_receipts", "location_id", "warehouse_id", "RESTRICT"),
    ("inventory_credit_notes", "location_id", "warehouse_id", "RESTRICT"),
]


def _fk_name(bind, table: str, column: str, referred: str) -> str | None:
    for fk in sa.inspect(bind).get_foreign_keys(table):
        if fk["constrained_columns"] == [column] and fk["referred_table"] == referred:
            return fk["name"]
    return None


def _repoint(bind, from_table, old, new, referred_from, referred_to, ondelete):
    fk = _fk_name(bind, from_table, old, referred_from)
    with op.batch_alter_table(from_table) as batch:
        if fk:
            batch.drop_constraint(fk, type_="foreignkey")
        batch.drop_index(f"ix_{from_table}_{old}")
        batch.alter_column(old, new_column_name=new)
    with op.batch_alter_table(from_table) as batch:
        batch.create_foreign_key(
            f"fk_{from_table}_{new}_{referred_to}", referred_to, [new], ["id"], ondelete=ondelete
        )
        batch.create_index(f"ix_{from_table}_{new}", [new])


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "inventory_warehouses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name_zh", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location_id", sa.Uuid(), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_inventory_warehouses_code"),
    )
    op.create_index("ix_inventory_warehouses_location_id", "inventory_warehouses", ["location_id"])

    referenced = " UNION ".join(f"SELECT {col} AS id FROM {table}" for table, col, _n, _o in COLUMNS)

    rows = bind.execute(
        sa.text(
            "SELECT l.id, l.code, l.name_zh, l.name_en, l.address, l.phone, l.is_active "
            f"FROM locations l WHERE l.id IN ({referenced}) ORDER BY l.created_at, l.id"
        )
    ).all()

    used_codes: set[str] = set()
    now = sa.func.now()
    warehouses = sa.table(
        "inventory_warehouses",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name_zh", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("address", sa.String()),
        sa.column("phone", sa.String()),
        sa.column("location_id", sa.Uuid()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    for row in rows:
        loc_id = row.id if isinstance(row.id, uuid.UUID) else uuid.UUID(str(row.id))
        code = (row.code or "").strip()[:20] or str(loc_id)[:8]
        if code in used_codes:
            code = str(loc_id)[:8]
        used_codes.add(code)
        bind.execute(
            sa.insert(warehouses).values(
                id=loc_id,
                code=code,
                name_zh=row.name_zh,
                name_en=row.name_en,
                address=row.address,
                phone=row.phone,
                location_id=loc_id,
                is_active=row.is_active,
                created_at=now,
                updated_at=now,
            )
        )

    # Drop constraints that name location_id before the rename. SQLite batch
    # recreates the table from reflected constraints and fails if those still
    # point at the old column. Transfers have no table (two movements).
    with op.batch_alter_table("inventory_stocks") as batch:
        batch.drop_constraint("uq_inventory_stocks_item_location", type_="unique")
    with op.batch_alter_table("inventory_counters") as batch:
        batch.drop_constraint("uq_inventory_counters_loc_type", type_="unique")
    with op.batch_alter_table("inventory_movements") as batch:
        batch.drop_index("ix_inventory_movements_item_loc_created")

    for table, old, new, ondelete in COLUMNS:
        _repoint(bind, table, old, new, "locations", "inventory_warehouses", ondelete)

    with op.batch_alter_table("inventory_stocks") as batch:
        batch.create_unique_constraint("uq_inventory_stocks_item_warehouse", ["item_id", "warehouse_id"])
    with op.batch_alter_table("inventory_counters") as batch:
        batch.create_unique_constraint("uq_inventory_counters_wh_type", ["warehouse_id", "doc_type"])
    with op.batch_alter_table("inventory_movements") as batch:
        batch.create_index(
            "ix_inventory_movements_item_wh_created", ["item_id", "warehouse_id", "created_at"]
        )


def downgrade() -> None:
    bind = op.get_bind()

    orphans = bind.execute(
        sa.text(
            "SELECT w.code FROM inventory_warehouses w "
            "WHERE w.id NOT IN (SELECT id FROM locations)"
        )
    ).all()
    if orphans:
        codes = ", ".join(r.code for r in orphans)
        raise RuntimeError(
            "Cannot downgrade 052: these warehouses have no matching attendance location "
            f"(created after the upgrade): {codes}. Remove them or create locations with the same ids first."
        )

    with op.batch_alter_table("inventory_movements") as batch:
        batch.drop_index("ix_inventory_movements_item_wh_created")
    with op.batch_alter_table("inventory_counters") as batch:
        batch.drop_constraint("uq_inventory_counters_wh_type", type_="unique")
    with op.batch_alter_table("inventory_stocks") as batch:
        batch.drop_constraint("uq_inventory_stocks_item_warehouse", type_="unique")

    for table, old, new, ondelete in COLUMNS:
        fk = _fk_name(bind, table, new, "inventory_warehouses")
        with op.batch_alter_table(table) as batch:
            if fk:
                batch.drop_constraint(fk, type_="foreignkey")
            batch.drop_index(f"ix_{table}_{new}")
            batch.alter_column(new, new_column_name=old)
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(f"fk_{table}_{old}_locations", "locations", [old], ["id"], ondelete=ondelete)
            batch.create_index(f"ix_{table}_{old}", [old])

    with op.batch_alter_table("inventory_stocks") as batch:
        batch.create_unique_constraint("uq_inventory_stocks_item_location", ["item_id", "location_id"])
    with op.batch_alter_table("inventory_counters") as batch:
        batch.create_unique_constraint("uq_inventory_counters_loc_type", ["location_id", "doc_type"])
    with op.batch_alter_table("inventory_movements") as batch:
        batch.create_index("ix_inventory_movements_item_loc_created", ["item_id", "location_id", "created_at"])

    op.drop_index("ix_inventory_warehouses_location_id", table_name="inventory_warehouses")
    op.drop_table("inventory_warehouses")
