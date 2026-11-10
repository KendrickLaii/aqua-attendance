"""Seed demo data for the inventory module into the dedicated demo database.

SAFETY: this script ONLY runs when DATABASE_URL / DATABASE_URL_SYNC point at a
database literally named ``attendance_inventory``. It rewrites the URLs from
apps/api/.env itself (never prints credentials) and aborts otherwise.

Run (PowerShell)::

    python seed_inventory.py            # seed (idempotent; exits if demo data exists)
    python seed_inventory.py --catalog      # seed ONLY the brands / sub-categories / products-with-variants
                                            # catalog (idempotent; skips if DEMO-TSHIRT exists)
    python seed_inventory.py --reset-demo   # delete ONLY the rows this script created (incl. --catalog data)

All business documents are created by driving the live HTTP API at
http://localhost:8010 so that ledgers, reservations, document numbers and
weighted-average costs are produced by the real code paths. Date columns that
are user-settable (order_date, receipt_date, issue_date, ...) are passed in the
payload; server-stamped movement ``created_at`` values are backdated via ORM
updates afterwards.
"""
import argparse
import asyncio
import itertools
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API_BASE = "http://localhost:8010"
DEMO_DB = "attendance_inventory"
DEMO = "[demo]"
DEMO_ADMIN_USERNAME = "demo_admin"
DEMO_ADMIN_PASSWORD = "Demo1234!"


def _load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = Path(__file__).resolve().parent / ".env"
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


def _configure_db_env() -> None:
    dotenv = _load_dotenv()
    for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
        url = dotenv.get(key)
        if not url:
            raise SystemExit(f"{key} missing from apps/api/.env")
        base = url.rsplit("/", 1)[0]
        os.environ[key] = f"{base}/{DEMO_DB}"
    db_name = os.environ["DATABASE_URL"].rsplit("/", 1)[-1].split("?")[0]
    if db_name != DEMO_DB:
        raise SystemExit(f"refusing to run: database is {db_name!r}, expected {DEMO_DB!r}")
    sync_name = os.environ["DATABASE_URL_SYNC"].rsplit("/", 1)[-1].split("?")[0]
    if sync_name != DEMO_DB:
        raise SystemExit(f"refusing to run: sync database is {sync_name!r}, expected {DEMO_DB!r}")


_configure_db_env()
os.environ.setdefault("APP_DISABLE_BACKGROUND_TASKS", "1")

import httpx  # noqa: E402
from sqlalchemy import delete, or_, select, update  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from app.models.inventory import (  # noqa: E402
    InventoryBrand,
    InventoryCategory,
    InventoryItem,
    InventoryMovement,
    InventoryProduct,
    InventoryStock,
    InventoryStocktake,
    InventoryStocktakeLine,
    InventoryWarehouse,
)
from app.models.inventory_invoicing import (  # noqa: E402
    InventoryCreditNote,
    InventoryCreditNoteLine,
    InventoryInvoice,
    InventoryInvoiceLine,
    InventoryReceipt,
)
from app.models.inventory_purchasing import (  # noqa: E402
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
    Supplier,
)
from app.models.inventory_sales import (  # noqa: E402
    Customer,
    DeliveryOrder,
    DeliveryOrderLine,
    SalesOrder,
    SalesOrderLine,
)
from app.models.location import Location  # noqa: E402
from app.models.notification import Notification  # noqa: E402
from app.models.unit import Unit  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth import hash_password  # noqa: E402

TODAY = date.today()


def d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


class Api:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(base_url=API_BASE, timeout=30)

    async def login(self, username: str, password: str) -> None:
        r = await self.client.post("/api/auth/login", json={"username": username, "password": password})
        if r.status_code != 200:
            raise SystemExit(f"login failed for {username}: {r.status_code} {r.text[:300]}")
        token = r.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {token}"

    async def __call__(self, method: str, path: str, **kw):
        r = await self.client.request(method, path, **kw)
        if r.status_code >= 400:
            raise SystemExit(f"{method} {path} -> {r.status_code}\n{r.text[:500]}")
        return r.json() if r.status_code != 204 else None

    async def get(self, path, **kw):
        return await self("GET", path, **kw)

    async def post(self, path, **kw):
        return await self("POST", path, **kw)

    async def patch(self, path, **kw):
        return await self("PATCH", path, **kw)

    async def aclose(self):
        await self.client.aclose()


ITEMS = [
    # sku, name_zh, name_en, cat, uom, cost, sale, reorder
    ("DEMO-BK-001", "數學講義 P4", "Math Worksheet P4", "教材", "本", 30, 55, 10),
    ("DEMO-BK-002", "英文文法練習簿", "English Grammar Workbook", "教材", "本", 25, 48, 10),
    ("DEMO-BK-003", "中文作文範本", "Chinese Composition Samples", "教材", "本", 28, 50, 8),
    ("DEMO-ST-001", "原子筆", "Ballpoint Pen", "文具", "支", 3, 8, 50),
    ("DEMO-ST-002", "修正帶", "Correction Tape", "文具", "個", 6, 15, 20),
    ("DEMO-ST-003", "文件夾", "Document Folder", "文具", "個", 4, 12, 15),
    ("DEMO-ST-004", "筆記簿", "Notebook", "文具", "本", 8, 20, 15),
    ("DEMO-PR-001", "小禮物公仔", "Mini Figurine", "獎品", "個", 12, 30, 5),
    ("DEMO-PR-002", "貼紙套裝", "Sticker Pack", "獎品", "套", 5, 15, 30),
]
CATEGORIES = [("教材", "Textbooks (demo)"), ("文具", "Stationery (demo)"), ("獎品", "Prizes (demo)")]

OPENING = {  # sku -> (qty@WF, qty@AB)
    "DEMO-BK-001": (60, 20), "DEMO-BK-002": (60, 20), "DEMO-BK-003": (40, 15),
    "DEMO-ST-001": (40, 20), "DEMO-ST-002": (60, 25), "DEMO-ST-003": (50, 20),
    "DEMO-ST-004": (60, 25), "DEMO-PR-001": (20, 10), "DEMO-PR-002": (25, 12),
}


async def ensure_admin(db) -> bool:
    user = (
        await db.execute(select(User).where(User.username == DEMO_ADMIN_USERNAME))
    ).scalar_one_or_none()
    hashed = hash_password(DEMO_ADMIN_PASSWORD)
    if user is None:
        db.add(User(
            username=DEMO_ADMIN_USERNAME,
            email="demo_admin@demo.local",
            hashed_password=hashed,
            full_name="Demo Admin",
            role="admin",
            is_active=True,
        ))
        await db.commit()
        return True
    if not user.is_active or user.role not in ("admin", "superadmin") or user.hashed_password != hashed:
        user.is_active = True
        user.role = "admin" if user.role not in ("admin", "superadmin") else user.role
        user.hashed_password = hashed
        await db.commit()
    return False


async def get_locations(db) -> tuple[Location, Location]:
    rows = (await db.execute(
        select(Location).where(Location.code.in_(["YT-WF", "YT-AB"]))
    )).scalars().all()
    by_code = {r.code: r for r in rows}
    created = False
    if "YT-WF" not in by_code:
        loc = Location(code="YT-WF", name_en="Wah Fu", name_zh="華富", location_type="branch", is_active=True)
        db.add(loc)
        by_code["YT-WF"] = loc
        created = True
    if "YT-AB" not in by_code:
        loc = Location(code="YT-AB", name_en="Aberdeen", name_zh="香港仔", location_type="branch", is_active=True)
        db.add(loc)
        by_code["YT-AB"] = loc
        created = True
    if created:
        await db.commit()
    for loc in (by_code["YT-WF"], by_code["YT-AB"]):
        await db.refresh(loc)
        existing = await db.get(InventoryWarehouse, loc.id)
        if existing:
            continue
        db.add(InventoryWarehouse(
            id=loc.id,
            code=(loc.code or str(loc.id)[:8])[:20],
            name_zh=loc.name_zh,
            name_en=loc.name_en,
            address=loc.address,
            phone=loc.phone,
            location_id=loc.id,
            is_active=loc.is_active,
        ))
    await db.commit()
    return by_code["YT-WF"], by_code["YT-AB"]


async def get_student_units(db) -> list[Unit]:
    units = (await db.execute(
        select(Unit).where(
            Unit.unit_type == "student", Unit.is_active == True,  # noqa: E712
            Unit.code.like("STU-%"),
        ).order_by(Unit.code).limit(3)
    )).scalars().all()
    if len(units) < 3:
        units += [u for u in (await db.execute(
            select(Unit).where(Unit.unit_type == "student", Unit.is_active == True)  # noqa: E712
            .order_by(Unit.code)
        )).scalars().all() if u not in units][: 3 - len(units)]
    if len(units) < 3:
        for i in range(3 - len(units)):
            unit = Unit(code=f"DEMO-STU-{i + 1:03d}", full_name=f"Demo Student {i + 1}",
                        unit_type="student", is_active=True, status="active")
            db.add(unit)
            units.append(unit)
        await db.commit()
    return units


async def seed() -> None:
    async with async_session_factory() as db:
        if (await db.execute(select(InventoryItem).where(InventoryItem.sku_code == "DEMO-BK-001"))).scalar_one_or_none():
            print("demo data already present")
            return
        created_admin = await ensure_admin(db)
        wf, ab = await get_locations(db)
        students = await get_student_units(db)

    api = Api()
    try:
        await api.login(DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD)
        inv = "/api/inventory"

        # --- categories + items ---
        cat_id: dict[str, str] = {}
        for name_zh, name_en in CATEGORIES:
            row = await api.post(f"{inv}/categories", json={"name_zh": name_zh, "name_en": name_en})
            cat_id[name_zh] = row["id"]
        item_id: dict[str, str] = {}
        for sku, zh, en, cat, uom, cost, sale, ro in ITEMS:
            row = await api.post(f"{inv}/items", json={
                "sku_code": sku, "name_zh": zh, "name_en": en, "category_id": cat_id[cat],
                "unit_of_measure": uom, "cost_price": cost, "sale_price": sale, "reorder_level": ro,
            })
            item_id[sku] = row["id"]

        # --- opening stock / write-offs / adjust / transfer / stocktake ---
        movement_ids: list[tuple[str, int]] = []  # (movement id, days_ago)
        for sku, (q_wf, q_ab) in OPENING.items():
            for loc, qty, ago in ((wf, q_wf, 60), (ab, q_ab, 58)):
                mv = await api.post(f"{inv}/movements", json={
                    "item_id": item_id[sku], "warehouse_id": str(loc.id), "type": "in",
                    "quantity": qty, "reason_code": "opening",
                    "reason": f"{DEMO} opening stock {loc.code}",
                })
                movement_ids.append((mv["id"], ago))

        adj = await api.post(f"{inv}/movements", json={
            "item_id": item_id["DEMO-ST-004"], "warehouse_id": str(wf.id), "type": "adjust",
            "quantity": OPENING["DEMO-ST-004"][0] + 4,
            "reason": f"{DEMO} recount +4",
        })
        movement_ids.append((adj["id"], 50))
        for sku, code, note, ago in (("DEMO-BK-003", "damage", "水浸損毀", 40), ("DEMO-ST-002", "gift", "贈送學生禮物", 35)):
            mv = await api.post(f"{inv}/movements", json={
                "item_id": item_id[sku], "warehouse_id": str(wf.id), "type": "out",
                "quantity": 3 if code == "damage" else 5, "reason_code": code,
                "reason": f"{DEMO} {note}",
            })
            movement_ids.append((mv["id"], ago))
        trf = await api.post(f"{inv}/transfers", json={
            "item_id": item_id["DEMO-BK-003"], "from_warehouse_id": str(wf.id),
            "to_warehouse_id": str(ab.id), "quantity": 10, "reason": f"{DEMO} 分校調撥",
        })
        movement_ids.append((trf["out_movement"]["id"], 30))
        movement_ids.append((trf["in_movement"]["id"], 30))
        st = await api.post(f"{inv}/stocktakes", json={
            "warehouse_id": str(ab.id), "item_ids": [item_id["DEMO-BK-001"], item_id["DEMO-BK-002"]],
            "note": f"{DEMO} 月結盤點(未完成)",
        })

        # --- suppliers + customers ---
        sup1 = await api.post(f"{inv}/suppliers", json={
            "code": "DEMO-SUP-01", "name_zh": "文華書局", "name_en": "Manhua Books",
            "contact_name": "陳生", "phone": "2345-6789", "payment_terms": "30 days",
        })
        sup2 = await api.post(f"{inv}/suppliers", json={
            "code": "DEMO-SUP-02", "name_zh": "卓越文具", "name_en": "Excel Stationery",
            "contact_name": "黃小姐", "phone": "2987-6543",
        })
        cust1 = await api.post(f"{inv}/customers/from-student/{students[0].id}")
        cust2 = await api.post(f"{inv}/customers/from-student/{students[1].id}")
        cust3 = await api.post(f"{inv}/customers", json={
            "code": "DEMO-CUST-01", "name_zh": "陽光書局有限公司", "name_en": "Sunshine Bookstore Ltd",
            "type": "company", "contact_name": "林經理", "phone": "2525-8899",
        })

        # --- purchasing ---
        po1 = await api.post(f"{inv}/purchase-orders", json={
            "supplier_id": sup1["id"], "warehouse_id": str(wf.id), "order_date": d(55),
            "expected_date": d(50), "notes": f"{DEMO} 教材補貨",
            "lines": [
                {"item_id": item_id["DEMO-BK-001"], "ordered_qty": 60, "unit_cost": 30},
                {"item_id": item_id["DEMO-BK-002"], "ordered_qty": 40, "unit_cost": 25},
            ],
        })
        await api.post(f"{inv}/purchase-orders/{po1['id']}/order")
        grn1 = await api.post(f"{inv}/goods-receipts", json={
            "po_id": po1["id"], "supplier_id": sup1["id"], "warehouse_id": str(wf.id),
            "receipt_date": d(50), "notes": f"{DEMO} 首批到貨",
            "lines": [
                {"item_id": item_id["DEMO-BK-001"], "qty": 30, "unit_cost": 30},
                {"item_id": item_id["DEMO-BK-002"], "qty": 40, "unit_cost": 25},
            ],
        })
        await api.post(f"{inv}/goods-receipts/{grn1['id']}/confirm")
        grn2 = await api.post(f"{inv}/goods-receipts", json={
            "po_id": po1["id"], "supplier_id": sup1["id"], "warehouse_id": str(wf.id),
            "receipt_date": d(45), "notes": f"{DEMO} 第二批到貨(成本上升)",
            "lines": [{"item_id": item_id["DEMO-BK-001"], "qty": 30, "unit_cost": 36}],
        })
        await api.post(f"{inv}/goods-receipts/{grn2['id']}/confirm")

        po2 = await api.post(f"{inv}/purchase-orders", json={
            "supplier_id": sup2["id"], "warehouse_id": str(wf.id), "order_date": d(35),
            "expected_date": d(5), "notes": f"{DEMO} 文具補貨(逾期未齊)",
            "lines": [
                {"item_id": item_id["DEMO-ST-001"], "ordered_qty": 200, "unit_cost": 3},
                {"item_id": item_id["DEMO-ST-002"], "ordered_qty": 60, "unit_cost": 6},
            ],
        })
        await api.post(f"{inv}/purchase-orders/{po2['id']}/order")
        grn3 = await api.post(f"{inv}/goods-receipts", json={
            "po_id": po2["id"], "supplier_id": sup2["id"], "warehouse_id": str(wf.id),
            "receipt_date": d(30), "notes": f"{DEMO} 部分到貨",
            "lines": [{"item_id": item_id["DEMO-ST-001"], "qty": 100, "unit_cost": 3}],
        })
        await api.post(f"{inv}/goods-receipts/{grn3['id']}/confirm")

        po3 = await api.post(f"{inv}/purchase-orders", json={
            "supplier_id": sup1["id"], "warehouse_id": str(ab.id), "order_date": d(3),
            "expected_date": d(-7), "notes": f"{DEMO} 草稿採購單",
            "lines": [{"item_id": item_id["DEMO-PR-001"], "ordered_qty": 30, "unit_cost": 12}],
        })

        prt = await api.post(f"{inv}/purchase-returns", json={
            "supplier_id": sup1["id"], "warehouse_id": str(wf.id), "grn_id": grn1["id"],
            "return_date": d(40), "notes": f"{DEMO} 次品退回",
            "lines": [{"item_id": item_id["DEMO-BK-002"], "qty": 5, "unit_cost": 25}],
        })
        await api.post(f"{inv}/purchase-returns/{prt['id']}/confirm")

        # --- sales orders ---
        # New flow: SO confirm reserves -> invoice issued from SO (issue deducts
        # stock) -> DO sub-documents record physical delivery only -> receipts.
        so_draft = await api.post(f"{inv}/sales-orders", json={
            "customer_id": cust3["id"], "warehouse_id": str(wf.id), "order_date": d(20),
            "notes": f"{DEMO} 草稿銷售單",
            "lines": [{"item_id": item_id["DEMO-ST-003"], "qty": 10, "unit_price": 12}],
        })
        await api.post(f"{inv}/sales-orders/{so_draft['id']}/proforma", json={"pf_valid_until": d(2)})

        # cust1 SO invoiced in two invoices (partial invoicing)
        so_conf = await api.post(f"{inv}/sales-orders", json={
            "customer_id": cust1["id"], "warehouse_id": str(wf.id), "order_date": d(20),
            "discount_amount": 20, "notes": f"{DEMO} 分批開票銷售單",
            "lines": [
                {"item_id": item_id["DEMO-BK-001"], "qty": 5, "unit_price": 55, "discount_amount": 10},
                {"item_id": item_id["DEMO-PR-001"], "qty": 3, "unit_price": 30},
            ],
        })
        await api.post(f"{inv}/sales-orders/{so_conf['id']}/confirm")
        await api.post(f"{inv}/sales-orders/{so_conf['id']}/proforma", json={"pf_valid_until": d(1)})

        conf_line = next(
            ln for ln in so_conf["lines"] if ln["item_id"] == item_id["DEMO-BK-001"]
        )
        # first invoice covers only the BK-001 line → paid in full + DO delivered
        inv_paid = await api.post(f"{inv}/invoices", json={
            "so_id": so_conf["id"], "issue_date": d(19), "notes": f"{DEMO} 已付清發票",
            "lines": [{"so_line_id": conf_line["id"], "qty": 5}],
        })
        await api.post(f"{inv}/invoices/{inv_paid['id']}/issue")
        do_full = await api.post(f"{inv}/delivery-orders", json={
            "invoice_id": inv_paid["id"], "delivery_date": d(18), "notes": f"{DEMO} 全數送貨",
        })
        await api.post(f"{inv}/delivery-orders/{do_full['id']}/confirm")
        await api.post(f"{inv}/receipts", json={
            "invoice_id": inv_paid["id"], "amount": inv_paid["total"], "paid_by": "cash",
            "receipt_date": d(15), "notes": f"{DEMO} 全數付款",
        })

        # second invoice covers the remaining PR-001 line → partial DO + partial payment
        inv_partial = await api.post(f"{inv}/invoices", json={
            "so_id": so_conf["id"], "issue_date": d(14), "notes": f"{DEMO} 部分付款發票",
        })
        await api.post(f"{inv}/invoices/{inv_partial['id']}/issue")
        do_partial = await api.post(f"{inv}/delivery-orders", json={
            "invoice_id": inv_partial["id"], "delivery_date": d(12),
            "notes": f"{DEMO} 先送兩份",
            "lines": [{"invoice_line_id": inv_partial["lines"][0]["id"], "qty": 2}],
        })
        await api.post(f"{inv}/delivery-orders/{do_partial['id']}/confirm")
        scn = await api.post(f"{inv}/credit-notes", json={
            "invoice_id": inv_partial["id"], "credit_date": d(11), "reason": f"{DEMO} 印刷瑕疵折讓",
            "lines": [{"invoice_line_id": inv_partial["lines"][0]["id"], "qty": 1, "restock": True}],
        })
        await api.post(f"{inv}/credit-notes/{scn['id']}/confirm")
        # derive payment amounts from the actual balance (never exceed it)
        inv_partial = await api.get(f"{inv}/invoices/{inv_partial['id']}")
        deposit = round(inv_partial["balance"] * 0.8, 2)
        await api.post(f"{inv}/receipts", json={
            "invoice_id": inv_partial["id"], "amount": deposit, "paid_by": "bank_transfer",
            "receipt_date": d(10), "reference_no": "TXN-8821", "notes": f"{DEMO} 訂金",
        })
        inv_partial = await api.get(f"{inv}/invoices/{inv_partial['id']}")
        receipt2v = await api.post(f"{inv}/receipts", json={
            "invoice_id": inv_partial["id"], "amount": round(inv_partial["balance"] * 0.5, 2),
            "paid_by": "cash", "receipt_date": d(9), "notes": f"{DEMO} 錯誤入帳後作廢",
        })
        await api.post(f"{inv}/receipts/{receipt2v['id']}/void")

        # issued invoice with nothing delivered yet
        so_nodel = await api.post(f"{inv}/sales-orders", json={
            "customer_id": cust2["id"], "warehouse_id": str(wf.id), "order_date": d(8),
            "notes": f"{DEMO} 已開票未送貨",
            "lines": [
                {"item_id": item_id["DEMO-BK-002"], "qty": 10, "unit_price": 48},
                {"item_id": item_id["DEMO-ST-004"], "qty": 5, "unit_price": 20},
            ],
        })
        await api.post(f"{inv}/sales-orders/{so_nodel['id']}/confirm")
        inv_nodel = await api.post(f"{inv}/invoices", json={
            "so_id": so_nodel["id"], "issue_date": d(6), "notes": f"{DEMO} 已開票未送貨發票",
        })
        await api.post(f"{inv}/invoices/{inv_nodel['id']}/issue")

        # unpaid overdue invoice (delivered, never paid)
        so_late = await api.post(f"{inv}/sales-orders", json={
            "customer_id": cust3["id"], "warehouse_id": str(wf.id), "order_date": d(50),
            "notes": f"{DEMO} 逾期未收款",
            "lines": [{"item_id": item_id["DEMO-BK-003"], "qty": 8, "unit_price": 50}],
        })
        await api.post(f"{inv}/sales-orders/{so_late['id']}/confirm")
        inv_late = await api.post(f"{inv}/invoices", json={
            "so_id": so_late["id"], "issue_date": d(45), "notes": f"{DEMO} 逾期未收款發票",
        })
        await api.post(f"{inv}/invoices/{inv_late['id']}/issue")
        do_late = await api.post(f"{inv}/delivery-orders", json={
            "invoice_id": inv_late["id"], "delivery_date": d(44), "notes": f"{DEMO} 已送貨未收款",
        })
        await api.post(f"{inv}/delivery-orders/{do_late['id']}/confirm")

        # draft invoice on the not-yet-delivered SO? so_nodel is fulfilled; use a
        # partially-invoiced SO instead
        so_draft_inv = await api.post(f"{inv}/sales-orders", json={
            "customer_id": cust2["id"], "warehouse_id": str(wf.id), "order_date": d(5),
            "notes": f"{DEMO} 部分開票中",
            "lines": [{"item_id": item_id["DEMO-ST-001"], "qty": 30, "unit_price": 8}],
        })
        await api.post(f"{inv}/sales-orders/{so_draft_inv['id']}/confirm")
        await api.post(f"{inv}/sales-orders/{so_draft_inv['id']}/proforma", json={"pf_valid_until": d(-30)})
        inv_draft = await api.post(f"{inv}/invoices", json={
            "so_id": so_draft_inv["id"], "notes": f"{DEMO} 草稿發票",
            "lines": [{"so_line_id": so_draft_inv["lines"][0]["id"], "qty": 10}],
        })

        inv_paid = await api.get(f"{inv}/invoices/{inv_paid['id']}")
        inv_partial = await api.get(f"{inv}/invoices/{inv_partial['id']}")
        inv_nodel = await api.get(f"{inv}/invoices/{inv_nodel['id']}")
        inv_late = await api.get(f"{inv}/invoices/{inv_late['id']}")

        # --- backdate movement created_at for demo rows ---
        doc_refs: dict[str, int] = {  # reference prefix -> days_ago
            f"GRN:{grn1['id']}": 50, f"GRN:{grn2['id']}": 45, f"GRN:{grn3['id']}": 30,
            f"PRT:{prt['id']}": 40,
            f"SI:{inv_paid['id']}": 19, f"SI:{inv_partial['id']}": 14,
            f"SI:{inv_nodel['id']}": 6, f"SI:{inv_late['id']}": 45,
            f"SCN:{scn['id']}": 11,
        }
        async with async_session_factory() as db:
            for mid, ago in movement_ids:
                await db.execute(
                    update(InventoryMovement).where(InventoryMovement.id == mid)
                    .values(created_at=datetime.now(timezone.utc) - timedelta(days=ago))
                )
            for prefix, ago in doc_refs.items():
                await db.execute(
                    update(InventoryMovement)
                    .where(InventoryMovement.reference.like(f"{prefix}:%"))
                    .values(created_at=datetime.now(timezone.utc) - timedelta(days=ago))
                )
            await db.commit()

        notify = await api.post(f"{inv}/alerts/notify")

        print("=== inventory demo seed done ===")
        print(f"admin login: {DEMO_ADMIN_USERNAME} / {DEMO_ADMIN_PASSWORD} ({'created' if created_admin else 'existing/updated'})")
        print(f"categories: {len(CATEGORIES)} | items: {len(ITEMS)} | warehouses: {wf.code}, {ab.code}")
        print(f"suppliers: {sup1['code']}, {sup2['code']} | customers: {cust1['name_zh']}, {cust2['name_zh']}, {cust3['name_zh']}")
        print(f"POs: {po1['po_no']}(received) {po2['po_no']}(partial, overdue) {po3['po_no']}(draft)")
        print(f"GRNs: {grn1['grn_no']} {grn2['grn_no']} {grn3['grn_no']} | PRT: {prt['prt_no']}(confirmed)")
        print(f"SOs: {so_draft['so_no']}(draft) {so_conf['so_no']}(fulfilled, 2 invoices) "
              f"{so_nodel['so_no']}(fulfilled, undelivered) {so_late['so_no']}(fulfilled, unpaid) "
              f"{so_draft_inv['so_no']}(partial, draft invoice)")
        print(f"DOs: {do_full['do_no']} {do_partial['do_no']}(partial) {do_late['do_no']} (all confirmed)")
        print(f"invoices: {inv_paid['invoice_no']}(paid) {inv_partial['invoice_no']}(partial) "
              f"{inv_nodel['invoice_no']}(unpaid, undelivered) {inv_late['invoice_no']}(unpaid, 45d) "
              f"+ draft {inv_draft['id']}")
        print(f"credit note: {scn['scn_no']}(confirmed, restock) | receipts: 3 posted incl. 1 voided")
        print(f"stocktake: {st['id']} draft at {ab.code}")
        print(f"notifications: {notify}")
    finally:
        await api.aclose()


HOUSE = ("自家品牌", "House brand (demo)")
BRANDS = [
    ("IKEA", "IKEA (demo)"),
    ("Nike", "Nike (demo)"),
    ("Adidas", "Adidas (demo)"),
    ("Pentel 飛龍", "Pentel (demo)"),
    ("Muji 無印良品", "Muji (demo)"),
    ("Casio", "Casio (demo)"),
    ("Apple", "Apple (demo)"),
    HOUSE,
]

# top-level (name_zh, name_en) -> [(sub name_zh, sub name_en)]
CATALOG_CATEGORIES = [
    (("校服", "Uniform (demo)"), [("上衣", "Tops (demo)"), ("褲", "Bottoms (demo)"), ("外套", "Jackets (demo)")]),
    (("文具", "Stationery (demo)"), [("筆", "Pens (demo)"), ("簿", "Notebooks (demo)"), ("計數機", "Calculators (demo)")]),
    (("家用電器", "Home Appliances (demo)"), [("智能手機", "Smartphones (demo)"), ("平板", "Tablets (demo)")]),
    (("運動用品", "Sports (demo)"), [("波", "Balls (demo)"), ("運動袋", "Bags (demo)")]),
]

# code, name_zh, name_en, brand, (top, sub), options, price(attrs), cost(attrs), reorder, barcoded, inactive
CATALOG_PRODUCTS = [
    ("DEMO-TSHIRT", "校服 T-shirt", "School T-shirt", "自家品牌", ("校服", "上衣"),
     {"尺寸": ["S", "M", "L", "XL"]}, lambda a: 85 if a["尺寸"] == "XL" else 80, lambda a: 35, 5, False),
    ("DEMO-POLO", "校服 Polo", "School Polo", "自家品牌", ("校服", "上衣"),
     {"尺寸": ["S", "M", "L"], "顏色": ["白", "藍"]}, lambda a: 120, lambda a: 50, 5, False),
    ("DEMO-PANTS", "校褲", "School Pants", "自家品牌", ("校服", "褲"),
     {"腰圍": ["26", "28", "30", "32"]}, lambda a: 150, lambda a: 65, 5, False),
    ("DEMO-JACKET", "運動外套", "Sports Jacket", "Nike", ("校服", "外套"),
     {"尺寸": ["S", "M", "L", "XL"], "顏色": ["黑", "深藍"]}, lambda a: 380, lambda a: 170, 5, False),
    ("DEMO-PEN", "啫喱筆 Energel", "Energel Gel Pen", "Pentel 飛龍", ("文具", "筆"),
     {"顏色": ["黑", "藍", "紅"], "筆嘴": ["0.5", "0.7"]}, lambda a: 12, lambda a: 5, 20, True),
    ("DEMO-NOTE", "筆記簿", "Notebook", "Muji 無印良品", ("文具", "簿"),
     {"尺寸": ["A5", "B5"], "款式": ["橫間", "方格", "空白"]}, lambda a: 18, lambda a: 8, 10, False),
    ("DEMO-IPAD", "iPad", "iPad", "Apple", ("家用電器", "平板"),
     {"容量": ["64GB", "256GB"], "顏色": ["銀", "太空灰"]},
     lambda a: 2799 if a["容量"] == "64GB" else 3999, lambda a: 2200 if a["容量"] == "64GB" else 3200, 5, True),
    ("DEMO-BALL", "籃球", "Basketball", "Adidas", ("運動用品", "波"),
     {"尺碼": ["5", "6", "7"]}, lambda a: 220, lambda a: 100, 5, False),
]
INACTIVE_PRODUCTS = {"DEMO-PANTS"}
INACTIVE_SKUS = {"DEMO-JACKET-XL-黑"}

# sku, name_zh, name_en, brand, (top, sub|None) | None, uom, sale, cost, reorder
CATALOG_ITEMS = [
    ("DEMO-CALC-FX50", "Casio fx-50FH II 計數機", "Casio fx-50FH II Calculator", "Casio", ("文具", "計數機"), "部", 168, 95, 5),
    ("DEMO-PHONE", "iPhone 16", "iPhone 16", "Apple", ("家用電器", "智能手機"), "部", 6899, 5600, 3),
    ("DEMO-BAG", "運動袋", "Sports Bag", "Nike", ("運動用品", "運動袋"), "個", 260, 120, 5),
    ("DEMO-LAMP", "IKEA 枱燈", "IKEA Desk Lamp", "IKEA", ("家用電器", None), "盞", 199, 90, 5),
    ("DEMO-MISC", "雜項貨品", "Misc Item", None, None, "件", 50, 20, 5),
]

STOCK_PATTERNS = [(30, 10), (8, 4), (3, 2), (0, 0), (20, 0), (2, 0), (15, 12), (0, 4)]


async def seed_catalog() -> None:
    async with async_session_factory() as db:
        if (await db.execute(select(InventoryProduct).where(InventoryProduct.code == "DEMO-TSHIRT"))).scalar_one_or_none():
            print("catalog demo data already present (DEMO-TSHIRT exists)")
            return
        created_admin = await ensure_admin(db)
        wf, ab = await get_locations(db)

    api = Api()
    try:
        await api.login(DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD)
        inv = "/api/inventory"

        brand_id: dict[str, str] = {b["name_zh"]: b["id"] for b in await api.get(f"{inv}/brands")}
        for name_zh, name_en in BRANDS:
            if name_zh not in brand_id:
                row = await api.post(f"{inv}/brands", json={"name_zh": name_zh, "name_en": name_en})
                brand_id[name_zh] = row["id"]

        existing = await api.get(f"{inv}/categories")
        cat_id: dict[tuple[str, str | None], str] = {
            (c["name_zh"], None): c["id"] for c in existing if not c["parent_id"]
        }
        parent_name = {c["id"]: c["name_zh"] for c in existing}
        for c in existing:
            if c["parent_id"]:
                cat_id[(parent_name[c["parent_id"]], c["name_zh"])] = c["id"]
        for (top_zh, top_en), subs in CATALOG_CATEGORIES:
            if (top_zh, None) not in cat_id:
                row = await api.post(f"{inv}/categories", json={"name_zh": top_zh, "name_en": top_en})
                cat_id[(top_zh, None)] = row["id"]
            for sub_zh, sub_en in subs:
                if (top_zh, sub_zh) not in cat_id:
                    row = await api.post(f"{inv}/categories", json={
                        "name_zh": sub_zh, "name_en": sub_en, "parent_id": cat_id[(top_zh, None)],
                    })
                    cat_id[(top_zh, sub_zh)] = row["id"]

        stock_targets: list[tuple[str, str]] = []  # (item id, sku code)
        barcode_seq = 4890000000000
        for code, name_zh, name_en, brand, (top, sub), options, price, cost, reorder, barcoded in CATALOG_PRODUCTS:
            keys = list(options)
            skus = []
            for combo in itertools.product(*(options[k] for k in keys)):
                attrs = dict(zip(keys, combo))
                barcode = None
                if barcoded:
                    barcode_seq += 1
                    barcode = str(barcode_seq)
                skus.append({
                    "sku_code": f"{code}-{'-'.join(combo)}",
                    "variant_attrs": attrs,
                    "sale_price": price(attrs),
                    "cost_price": cost(attrs),
                    "barcode": barcode,
                    "reorder_level": reorder,
                    "is_active": True,
                })
            product = await api.post(f"{inv}/products", json={
                "code": code, "name_zh": name_zh, "name_en": name_en,
                "brand_id": brand_id[brand], "category_id": cat_id[(top, sub)],
                "unit_of_measure": "件", "options": options, "skus": skus,
            })
            stock_targets += [(s["id"], s["sku_code"]) for s in product["skus"]]

        for sku, name_zh, name_en, brand, cat, uom, sale, cost, reorder in CATALOG_ITEMS:
            row = await api.post(f"{inv}/items", json={
                "sku_code": sku, "name_zh": name_zh, "name_en": name_en,
                "brand_id": brand_id[brand] if brand else None,
                "category_id": cat_id[cat] if cat else None,
                "unit_of_measure": uom, "sale_price": sale, "cost_price": cost, "reorder_level": reorder,
            })
            stock_targets.append((row["id"], sku))

        movements = 0
        for index, (item_id, _sku) in enumerate(stock_targets):
            for loc, qty in zip((wf, ab), STOCK_PATTERNS[index % len(STOCK_PATTERNS)]):
                if qty <= 0:
                    continue
                await api.post(f"{inv}/movements", json={
                    "item_id": item_id, "warehouse_id": str(loc.id), "type": "in",
                    "quantity": qty, "reason_code": "opening",
                    "reason": f"{DEMO} opening stock {loc.code}",
                })
                movements += 1

        # deactivate last: movements are rejected for inactive items
        products = {p["code"]: p for p in await api.get(f"{inv}/products", params={"page_size": 200})}
        for code in INACTIVE_PRODUCTS:
            await api.patch(f"{inv}/products/{products[code]['id']}", json={"is_active": False})
        for sku in INACTIVE_SKUS:
            sku_id = next(s["id"] for p in products.values() for s in p["skus"] if s["sku_code"] == sku)
            await api.patch(f"{inv}/items/{sku_id}", json={"is_active": False})

        print("=== inventory catalog demo seed done ===")
        print(f"admin login: {DEMO_ADMIN_USERNAME} / {DEMO_ADMIN_PASSWORD} ({'created' if created_admin else 'existing/updated'})")
        sku_total = sum(len(p["skus"]) for p in products.values() if p["code"].startswith("DEMO-"))
        print(f"brands: {len(BRANDS)} | categories: {sum(1 + len(s) for _t, s in CATALOG_CATEGORIES)} "
              f"| products: {len(CATALOG_PRODUCTS)} ({sku_total} SKUs) | standalone items: {len(CATALOG_ITEMS)} "
              f"| opening-stock movements: {movements}")
        print(f"inactive: products {sorted(INACTIVE_PRODUCTS)}, SKUs {sorted(INACTIVE_SKUS)}")
    finally:
        await api.aclose()


async def _reset_catalog(db) -> None:
    """Remove catalog demo rows. Items/stocks are already removed by the caller."""
    await db.execute(delete(InventoryProduct).where(InventoryProduct.code.like("DEMO-%")))

    referenced_brands = select(InventoryItem.brand_id).where(InventoryItem.brand_id.is_not(None)).union(
        select(InventoryProduct.brand_id).where(InventoryProduct.brand_id.is_not(None))
    )
    await db.execute(delete(InventoryBrand).where(
        InventoryBrand.name_en.like("%(demo)%"), InventoryBrand.id.not_in(referenced_brands)))

    # children first; keep categories still used by real items/products or still having real children
    for children in (True, False):
        used = select(InventoryItem.category_id).where(InventoryItem.category_id.is_not(None)).union(
            select(InventoryProduct.category_id).where(InventoryProduct.category_id.is_not(None)),
            select(InventoryCategory.parent_id).where(InventoryCategory.parent_id.is_not(None)),
        )
        cond = InventoryCategory.parent_id.is_not(None) if children else InventoryCategory.parent_id.is_(None)
        await db.execute(delete(InventoryCategory).where(
            InventoryCategory.name_en.like("%(demo)%"), cond, InventoryCategory.id.not_in(used)))


async def reset_demo() -> None:
    """Delete ONLY rows created by seed(): anything marked with [demo] in
    notes/reason, DEMO- prefixed codes, and rows referencing those documents."""
    async with async_session_factory() as db:
        demo_docs: dict[type, str] = {
            SalesOrder: "notes", DeliveryOrder: "notes", InventoryInvoice: "notes",
            InventoryReceipt: "notes", PurchaseOrder: "notes", GoodsReceipt: "notes",
            PurchaseReturn: "notes", InventoryStocktake: "note",
        }
        ids: dict[type, set] = {}
        for model, col in demo_docs.items():
            rows = (await db.execute(
                select(model.id).where(getattr(model, col).like(f"%{DEMO}%"))
            )).scalars().all()
            ids[model] = set(rows)
        scns = (await db.execute(
            select(InventoryCreditNote.id).where(InventoryCreditNote.reason.like(f"%{DEMO}%"))
        )).scalars().all()
        ids[InventoryCreditNote] = set(scns)

        customer_ids = set((await db.execute(
            select(SalesOrder.customer_id).where(SalesOrder.id.in_(ids[SalesOrder] or {None}))
        )).scalars().all())
        customer_ids |= set((await db.execute(
            select(InventoryInvoice.customer_id).where(InventoryInvoice.id.in_(ids[InventoryInvoice] or {None}))
        )).scalars().all())
        customer_ids.discard(None)

        ref_ids = set()
        for model in (PurchaseOrder, SalesOrder, InventoryInvoice, DeliveryOrder,
                      GoodsReceipt, PurchaseReturn, InventoryCreditNote, InventoryStocktake):
            ref_ids |= ids[model]

        demo_items = set((await db.execute(
            select(InventoryItem.id).where(InventoryItem.sku_code.like("DEMO-%"))
        )).scalars().all())

        # notifications created by the demo alert run reference demo doc ids;
        # low-stock alerts use ref "<item_id>:<warehouse_id>"
        notif_refs = {str(x) for x in ref_ids} | {str(x) for x in demo_items}
        notif = (await db.execute(select(Notification.id, Notification.extra_data))).all()
        notif_ids = [
            nid for nid, extra in notif
            if isinstance(extra, dict) and extra.get("inventory_alert")
            and str(extra.get("ref", "")).split(":")[0] in notif_refs
        ]
        if notif_ids:
            await db.execute(delete(Notification).where(Notification.id.in_(notif_ids)))

        await db.execute(delete(InventoryCreditNoteLine).where(
            InventoryCreditNoteLine.scn_id.in_(ids[InventoryCreditNote] or {None})))
        await db.execute(delete(InventoryCreditNote).where(
            InventoryCreditNote.id.in_(ids[InventoryCreditNote] or {None})))
        await db.execute(delete(InventoryReceipt).where(
            InventoryReceipt.id.in_(ids[InventoryReceipt] or {None})))
        # DOs are sub-documents of invoices (RESTRICT) — remove them first
        await db.execute(delete(DeliveryOrderLine).where(
            DeliveryOrderLine.do_id.in_(ids[DeliveryOrder] or {None})))
        await db.execute(delete(DeliveryOrder).where(
            DeliveryOrder.id.in_(ids[DeliveryOrder] or {None})))
        await db.execute(delete(InventoryInvoiceLine).where(
            InventoryInvoiceLine.invoice_id.in_(ids[InventoryInvoice] or {None})))
        await db.execute(delete(InventoryInvoice).where(
            InventoryInvoice.id.in_(ids[InventoryInvoice] or {None})))
        await db.execute(delete(SalesOrderLine).where(
            SalesOrderLine.so_id.in_(ids[SalesOrder] or {None})))
        await db.execute(delete(SalesOrder).where(
            SalesOrder.id.in_(ids[SalesOrder] or {None})))
        await db.execute(delete(PurchaseReturnLine).where(
            PurchaseReturnLine.prt_id.in_(ids[PurchaseReturn] or {None})))
        await db.execute(delete(PurchaseReturn).where(
            PurchaseReturn.id.in_(ids[PurchaseReturn] or {None})))
        await db.execute(delete(GoodsReceiptLine).where(
            GoodsReceiptLine.grn_id.in_(ids[GoodsReceipt] or {None})))
        await db.execute(delete(GoodsReceipt).where(
            GoodsReceipt.id.in_(ids[GoodsReceipt] or {None})))
        await db.execute(delete(PurchaseOrderLine).where(
            PurchaseOrderLine.po_id.in_(ids[PurchaseOrder] or {None})))
        await db.execute(delete(PurchaseOrder).where(
            PurchaseOrder.id.in_(ids[PurchaseOrder] or {None})))
        await db.execute(delete(InventoryStocktakeLine).where(
            InventoryStocktakeLine.stocktake_id.in_(ids[InventoryStocktake] or {None})))
        await db.execute(delete(InventoryStocktake).where(
            InventoryStocktake.id.in_(ids[InventoryStocktake] or {None})))

        # movements: demo reason text or references pointing at demo docs
        demo_ids_str = [str(x) for x in ref_ids]
        if demo_ids_str:
            cond = InventoryMovement.reason.like(f"%{DEMO}%")
            cond = or_(cond, *[
                InventoryMovement.reference.like(f"%:{did}:%") |
                InventoryMovement.reference.like(f"{did}:%")
                for did in demo_ids_str
            ])
            await db.execute(delete(InventoryMovement).where(cond))
        else:
            await db.execute(delete(InventoryMovement).where(InventoryMovement.reason.like(f"%{DEMO}%")))

        if demo_items:
            await db.execute(delete(InventoryStock).where(InventoryStock.item_id.in_(demo_items)))
            await db.execute(delete(InventoryItem).where(InventoryItem.id.in_(demo_items)))
        await _reset_catalog(db)
        await db.execute(delete(Supplier).where(Supplier.code.like("DEMO-%")))
        if customer_ids:
            await db.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        await db.execute(delete(Customer).where(Customer.code.like("DEMO-%")))

        await db.commit()
        print("demo rows removed: "
              + ", ".join(f"{m.__tablename__}={len(v)}" for m, v in ids.items() if v))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed inventory demo data (attendance_inventory only)")
    parser.add_argument("--reset-demo", action="store_true", help="delete only rows created by this seed")
    parser.add_argument("--catalog", action="store_true", help="seed only the brands/categories/products catalog data")
    args = parser.parse_args()
    if args.reset_demo:
        asyncio.run(reset_demo())
    elif args.catalog:
        asyncio.run(seed_catalog())
    else:
        asyncio.run(seed())


if __name__ == "__main__":
    main()
