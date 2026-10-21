import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.inventory import InventoryItem
from app.models.inventory_purchasing import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
    Supplier,
)
from app.models.inventory import InventoryStock
from app.models.location import Location
from app.schemas.inventory_purchasing import (
    GoodsReceiptCreate,
    GoodsReceiptLineIn,
    GoodsReceiptOut,
    GoodsReceiptUpdate,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderUpdate,
    PurchaseReturnCreate,
    PurchaseReturnOut,
    PurchaseReturnUpdate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from app.services import audit_log as audit_log_svc
from app.services import doc_numbers as doc_numbers_svc
from app.services import inventory as inventory_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def _assert_location_exists(db: DB, location_id: uuid.UUID) -> None:
    result = await db.execute(select(Location.id).where(Location.id == location_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")


async def _get_supplier_or_422(db: DB, supplier_id: uuid.UUID) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=422, detail="supplier_id does not reference an existing supplier")
    return supplier


async def _get_item_or_422(db: DB, item_id: uuid.UUID) -> InventoryItem:
    item = await db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=422, detail=f"unknown item_id: {item_id}")
    return item


async def _get_po_or_404(db: DB, po_id: uuid.UUID) -> PurchaseOrder:
    po = await db.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


async def _get_grn_or_404(db: DB, grn_id: uuid.UUID) -> GoodsReceipt:
    grn = await db.get(GoodsReceipt, grn_id)
    if not grn:
        raise HTTPException(status_code=404, detail="Goods receipt not found")
    return grn


async def _get_prt_or_404(db: DB, prt_id: uuid.UUID) -> PurchaseReturn:
    prt = await db.get(PurchaseReturn, prt_id)
    if not prt:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    return prt


async def _po_lines(db: DB, po_id: uuid.UUID) -> list[PurchaseOrderLine]:
    return list(
        (
            await db.execute(
                select(PurchaseOrderLine)
                .where(PurchaseOrderLine.po_id == po_id)
                .order_by(PurchaseOrderLine.id)
            )
        ).scalars().all()
    )


async def _grn_lines(db: DB, grn_id: uuid.UUID) -> list[GoodsReceiptLine]:
    return list(
        (
            await db.execute(
                select(GoodsReceiptLine)
                .where(GoodsReceiptLine.grn_id == grn_id)
                .order_by(GoodsReceiptLine.id)
            )
        ).scalars().all()
    )


async def _prt_lines(db: DB, prt_id: uuid.UUID) -> list[PurchaseReturnLine]:
    return list(
        (
            await db.execute(
                select(PurchaseReturnLine)
                .where(PurchaseReturnLine.prt_id == prt_id)
                .order_by(PurchaseReturnLine.id)
            )
        ).scalars().all()
    )


async def _items_map(db: DB, lines) -> dict[uuid.UUID, InventoryItem]:
    ids = {line.item_id for line in lines}
    if not ids:
        return {}
    result = await db.execute(select(InventoryItem).where(InventoryItem.id.in_(ids)))
    return {item.id: item for item in result.scalars().all()}


async def _po_detail(db: DB, po: PurchaseOrder) -> dict:
    lines = await _po_lines(db, po.id)
    supplier = await db.get(Supplier, po.supplier_id)
    location = await db.get(Location, po.location_id)
    out = {
        f: getattr(po, f)
        for f in PurchaseOrderOut.model_fields
        if f not in ("lines", "supplier_name", "location_name")
    }
    out["lines"] = lines
    out["supplier_name"] = supplier.name_zh if supplier else None
    out["location_name"] = location.name_en if location else None
    return out


async def _grn_detail(db: DB, grn: GoodsReceipt) -> dict:
    lines = await _grn_lines(db, grn.id)
    items = await _items_map(db, lines)
    supplier = await db.get(Supplier, grn.supplier_id)
    location = await db.get(Location, grn.location_id)
    po = await db.get(PurchaseOrder, grn.po_id) if grn.po_id else None
    out = {
        f: getattr(grn, f)
        for f in GoodsReceiptOut.model_fields
        if f not in ("lines", "supplier_name", "location_name", "po_no")
    }
    out["lines"] = [
        {
            "id": line.id,
            "item_id": line.item_id,
            "po_line_id": line.po_line_id,
            "qty": line.qty,
            "unit_cost": line.unit_cost,
            "sku_code": items[line.item_id].sku_code if line.item_id in items else None,
            "name_zh": items[line.item_id].name_zh if line.item_id in items else None,
        }
        for line in lines
    ]
    out["supplier_name"] = supplier.name_zh if supplier else None
    out["location_name"] = location.name_en if location else None
    out["po_no"] = po.po_no if po else None
    return out


async def _prt_detail(db: DB, prt: PurchaseReturn) -> dict:
    lines = await _prt_lines(db, prt.id)
    items = await _items_map(db, lines)
    supplier = await db.get(Supplier, prt.supplier_id)
    location = await db.get(Location, prt.location_id)
    grn = await db.get(GoodsReceipt, prt.grn_id) if prt.grn_id else None
    out = {
        f: getattr(prt, f)
        for f in PurchaseReturnOut.model_fields
        if f not in ("lines", "supplier_name", "location_name", "grn_no")
    }
    out["lines"] = [
        {
            "id": line.id,
            "item_id": line.item_id,
            "qty": line.qty,
            "unit_cost": line.unit_cost,
            "sku_code": items[line.item_id].sku_code if line.item_id in items else None,
            "name_zh": items[line.item_id].name_zh if line.item_id in items else None,
        }
        for line in lines
    ]
    out["supplier_name"] = supplier.name_zh if supplier else None
    out["location_name"] = location.name_en if location else None
    out["grn_no"] = grn.grn_no if grn else None
    return out


def _po_line_amount(ordered_qty: int, unit_cost: float, discount_amount: float) -> Decimal:
    return max(Decimal("0"), Decimal(str(ordered_qty)) * Decimal(str(unit_cost)) - Decimal(str(discount_amount)))


def _po_total(lines: list[PurchaseOrderLine], header_discount: float) -> Decimal:
    subtotal = sum((Decimal(str(line.amount)) for line in lines), Decimal("0"))
    return max(Decimal("0"), subtotal - Decimal(str(header_discount)))


async def _build_po_lines(db: DB, po: PurchaseOrder, line_inputs) -> list[PurchaseOrderLine]:
    lines = []
    for line_in in line_inputs:
        item = await _get_item_or_422(db, line_in.item_id)
        amount = _po_line_amount(line_in.ordered_qty, line_in.unit_cost, line_in.discount_amount)
        line = PurchaseOrderLine(
            po=po,
            item_id=item.id,
            sku_code=item.sku_code,
            name_zh=item.name_zh,
            ordered_qty=line_in.ordered_qty,
            received_qty=0,
            unit_cost=line_in.unit_cost,
            discount_amount=line_in.discount_amount,
            amount=amount,
        )
        db.add(line)
        lines.append(line)
    return lines


async def _recompute_po_status(db: DB, po: PurchaseOrder) -> None:
    if po.status in ("draft", "cancelled"):
        return
    lines = (
        await db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id))
    ).scalars().all()
    if lines and all(line.received_qty >= line.ordered_qty for line in lines):
        po.status = "received"
    elif any(line.received_qty > 0 for line in lines):
        po.status = "partial"
    else:
        po.status = "ordered"


async def _validate_grn_lines_against_po(
    db: DB, po: PurchaseOrder, line_inputs, allow_over_receipt: bool
) -> dict[uuid.UUID, PurchaseOrderLine]:
    po_lines = (
        await db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id))
    ).scalars().all()
    by_id = {line.id: line for line in po_lines}
    by_item = {line.item_id: line for line in po_lines}
    resolved: dict[uuid.UUID, PurchaseOrderLine] = {}
    for line_in in line_inputs:
        po_line = None
        if line_in.po_line_id:
            po_line = by_id.get(line_in.po_line_id)
            if po_line is None:
                raise HTTPException(status_code=422, detail=f"po_line_id {line_in.po_line_id} not on this PO")
        else:
            po_line = by_item.get(line_in.item_id)
        if po_line is None:
            raise HTTPException(
                status_code=422, detail=f"item {line_in.item_id} is not on PO {po.po_no}"
            )
        if not allow_over_receipt and po_line.received_qty + line_in.qty > po_line.ordered_qty:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"over-receipt for {po_line.sku_code}: ordered {po_line.ordered_qty}, "
                    f"received {po_line.received_qty}, this GRN {line_in.qty}"
                ),
            )
        resolved[po_line.id] = po_line
    return resolved


# ---- Suppliers ----


@router.get("/suppliers", response_model=list[SupplierOut])
async def list_suppliers(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[Supplier]:
    clauses = []
    if is_active is not None:
        clauses.append(Supplier.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(Supplier.code, search),
                ilike_contains(Supplier.name_zh, search),
                ilike_contains(Supplier.name_en, search),
                ilike_contains(Supplier.contact_name, search),
            )
        )

    count_q = select(func.count()).select_from(Supplier)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(Supplier)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(Supplier.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(body: SupplierCreate, _admin: AdminOnly, db: DB) -> Supplier:
    exists = await db.execute(select(Supplier).where(Supplier.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Supplier code already exists")
    supplier = Supplier(**body.model_dump())
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="suppliers",
        record_id=supplier.id,
        new_values=body.model_dump(),
        description=f"Created supplier {supplier.code} {supplier.name_zh}",
    )
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(supplier_id: uuid.UUID, _admin: AdminOnly, db: DB) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier(supplier_id: uuid.UUID, body: SupplierUpdate, _admin: AdminOnly, db: DB) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    update_data = body.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(
            select(Supplier).where(Supplier.code == new_code, Supplier.id != supplier_id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Supplier code already exists")

    old_values = {field: getattr(supplier, field) for field in update_data}
    for field, value in update_data.items():
        setattr(supplier, field, value)
    await db.commit()
    await db.refresh(supplier)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="suppliers",
        record_id=supplier_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated supplier {supplier.code} {supplier.name_zh}",
    )
    return supplier


# ---- Purchase orders ----


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
async def list_purchase_orders(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    supplier_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    clauses = []
    if supplier_id is not None:
        clauses.append(PurchaseOrder.supplier_id == supplier_id)
    if location_id is not None:
        clauses.append(PurchaseOrder.location_id == location_id)
    if status is not None:
        clauses.append(PurchaseOrder.status == status)
    if date_from is not None:
        clauses.append(PurchaseOrder.order_date >= date_from)
    if date_to is not None:
        clauses.append(PurchaseOrder.order_date <= date_to)

    count_q = select(func.count()).select_from(PurchaseOrder)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(PurchaseOrder)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [await _po_detail(db, po) for po in result.scalars().all()]


@router.post("/purchase-orders", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(body: PurchaseOrderCreate, _admin: AdminOnly, db: DB) -> dict:
    await _get_supplier_or_422(db, body.supplier_id)
    await _assert_location_exists(db, body.location_id)

    po_no = await doc_numbers_svc.allocate_doc_no(db, location_id=body.location_id, doc_type="PO")
    po = PurchaseOrder(
        po_no=po_no,
        supplier_id=body.supplier_id,
        location_id=body.location_id,
        order_date=body.order_date,
        expected_date=body.expected_date,
        discount_amount=body.discount_amount,
        notes=body.notes,
        created_by=_admin.id,
    )
    db.add(po)
    lines = await _build_po_lines(db, po, body.lines)
    db.add_all(lines)
    po.total = _po_total(lines, po.discount_amount)
    await db.flush()
    po_id = po.id
    await db.commit()

    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    po = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="purchase_orders",
        record_id=po.id,
        new_values={**body.model_dump(), "po_no": po_no, "total": po.total},
        description=f"Created purchase order {po_no}",
    )
    return await _po_detail(db, po)


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
async def get_purchase_order(po_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    po = await _get_po_or_404(db, po_id)
    return await _po_detail(db, po)


@router.patch("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
async def update_purchase_order(
    po_id: uuid.UUID, body: PurchaseOrderUpdate, _admin: AdminOnly, db: DB
) -> dict:
    po = await _get_po_or_404(db, po_id)
    if po.status != "draft":
        raise HTTPException(status_code=409, detail=f"purchase order is {po.status}; only drafts can be edited")

    update_data = body.model_dump(exclude_unset=True)
    old_values: dict = {}
    if "supplier_id" in update_data:
        await _get_supplier_or_422(db, update_data["supplier_id"])
    if "location_id" in update_data:
        await _assert_location_exists(db, update_data["location_id"])
    for field in ("supplier_id", "location_id", "order_date", "expected_date", "discount_amount", "notes"):
        if field in update_data:
            old_values[field] = getattr(po, field)
            setattr(po, field, update_data[field])

    if "lines" in update_data and update_data["lines"] is not None:
        existing = await _po_lines(db, po_id)
        old_values["lines"] = [
            {"item_id": line.item_id, "ordered_qty": line.ordered_qty} for line in existing
        ]
        for line in existing:
            await db.delete(line)
        await db.flush()
        lines = await _build_po_lines(db, po, body.lines)
        db.add_all(lines)
        po.total = _po_total(lines, po.discount_amount)
    else:
        await db.flush()
        po.total = _po_total(await _po_lines(db, po_id), po.discount_amount)

    await db.commit()
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    po = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="purchase_orders",
        record_id=po_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated purchase order {po.po_no}",
    )
    return await _po_detail(db, po)


@router.delete("/purchase-orders/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(po_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    po = await _get_po_or_404(db, po_id)
    if po.status != "draft":
        raise HTTPException(status_code=409, detail=f"purchase order is {po.status}; only drafts can be deleted")
    po_no = po.po_no
    await db.delete(po)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="purchase_orders",
        record_id=po_id,
        description=f"Deleted draft purchase order {po_no}",
    )


@router.post("/purchase-orders/{po_id}/order", response_model=PurchaseOrderOut)
async def order_purchase_order(po_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    po = await _get_po_or_404(db, po_id)
    if po.status == "ordered":
        return await _po_detail(db, po)
    if po.status != "draft":
        raise HTTPException(status_code=409, detail=f"purchase order is {po.status}; cannot order")
    if not await _po_lines(db, po_id):
        raise HTTPException(status_code=422, detail="purchase order has no lines")
    po.status = "ordered"
    await db.commit()
    await db.refresh(po)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="purchase_orders",
        record_id=po_id,
        old_values={"status": "draft"},
        new_values={"status": "ordered"},
        description=f"Ordered purchase order {po.po_no}",
    )
    return await _po_detail(db, po)


@router.post("/purchase-orders/{po_id}/cancel", response_model=PurchaseOrderOut)
async def cancel_purchase_order(po_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    po = await _get_po_or_404(db, po_id)
    if po.status == "cancelled":
        return await _po_detail(db, po)
    if po.status not in ("draft", "ordered", "partial"):
        raise HTTPException(status_code=409, detail=f"purchase order is {po.status}; cannot cancel")
    confirmed_grn = await db.execute(
        select(GoodsReceipt.id).where(
            GoodsReceipt.po_id == po_id, GoodsReceipt.status == "confirmed"
        ).limit(1)
    )
    if confirmed_grn.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="purchase order has confirmed goods receipts")
    old_status = po.status
    po.status = "cancelled"
    await db.commit()
    await db.refresh(po)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="purchase_orders",
        record_id=po_id,
        old_values={"status": old_status},
        new_values={"status": "cancelled"},
        description=f"Cancelled purchase order {po.po_no}",
    )
    return await _po_detail(db, po)


# ---- Goods receipts ----


@router.get("/goods-receipts", response_model=list[GoodsReceiptOut])
async def list_goods_receipts(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    supplier_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    po_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    clauses = []
    if supplier_id is not None:
        clauses.append(GoodsReceipt.supplier_id == supplier_id)
    if location_id is not None:
        clauses.append(GoodsReceipt.location_id == location_id)
    if po_id is not None:
        clauses.append(GoodsReceipt.po_id == po_id)
    if status is not None:
        clauses.append(GoodsReceipt.status == status)
    if date_from is not None:
        clauses.append(GoodsReceipt.receipt_date >= date_from)
    if date_to is not None:
        clauses.append(GoodsReceipt.receipt_date <= date_to)

    count_q = select(func.count()).select_from(GoodsReceipt)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(GoodsReceipt)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(GoodsReceipt.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [await _grn_detail(db, grn) for grn in result.scalars().all()]


@router.post("/goods-receipts", response_model=GoodsReceiptOut, status_code=status.HTTP_201_CREATED)
async def create_goods_receipt(body: GoodsReceiptCreate, _admin: AdminOnly, db: DB) -> dict:
    await _get_supplier_or_422(db, body.supplier_id)
    await _assert_location_exists(db, body.location_id)

    po: PurchaseOrder | None = None
    po_lines: dict[uuid.UUID, PurchaseOrderLine] = {}
    if body.po_id:
        po = await _get_po_or_404(db, body.po_id)
        if po.supplier_id != body.supplier_id or po.location_id != body.location_id:
            raise HTTPException(status_code=422, detail="supplier_id/location_id must match the PO")
        if po.status not in ("ordered", "partial"):
            raise HTTPException(status_code=422, detail=f"PO {po.po_no} is {po.status}; cannot receive")

    line_inputs: list[GoodsReceiptLineIn] = list(body.lines)
    if po and not line_inputs:
        po_lines_all = list(
            (
                await db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id))
            ).scalars().all()
        )
        line_inputs = [
            GoodsReceiptLineIn(
                item_id=line.item_id,
                qty=line.ordered_qty - line.received_qty,
                unit_cost=float(line.unit_cost),
                po_line_id=line.id,
            )
            for line in po_lines_all
            if line.ordered_qty - line.received_qty > 0
        ]
        if not line_inputs:
            raise HTTPException(status_code=422, detail="PO is fully received")

    if not line_inputs:
        raise HTTPException(status_code=422, detail="a goods receipt needs at least one line")

    for line_in in line_inputs:
        await _get_item_or_422(db, line_in.item_id)
    po_line_by_item: dict[uuid.UUID, uuid.UUID] = {}
    if po:
        resolved = await _validate_grn_lines_against_po(db, po, line_inputs, body.allow_over_receipt)
        po_line_by_item = {pl.item_id: pl.id for pl in resolved.values()}

    grn_no = await doc_numbers_svc.allocate_doc_no(db, location_id=body.location_id, doc_type="GRN")
    grn = GoodsReceipt(
        grn_no=grn_no,
        po_id=body.po_id,
        supplier_id=body.supplier_id,
        location_id=body.location_id,
        receipt_date=body.receipt_date,
        notes=body.notes,
        created_by=_admin.id,
    )
    db.add(grn)
    lines = []
    for line_in in line_inputs:
        po_line_id = line_in.po_line_id or po_line_by_item.get(line_in.item_id)
        lines.append(
            GoodsReceiptLine(
                grn=grn,
                po_line_id=po_line_id,
                item_id=line_in.item_id,
                qty=line_in.qty,
                unit_cost=line_in.unit_cost,
            )
        )
    db.add_all(lines)
    await db.flush()
    grn_id = grn.id
    await db.commit()

    result = await db.execute(select(GoodsReceipt).where(GoodsReceipt.id == grn_id))
    grn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="goods_receipts",
        record_id=grn.id,
        new_values={**body.model_dump(), "grn_no": grn_no},
        description=f"Created goods receipt {grn_no}",
    )
    return await _grn_detail(db, grn)


@router.get("/goods-receipts/{grn_id}", response_model=GoodsReceiptOut)
async def get_goods_receipt(grn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    grn = await _get_grn_or_404(db, grn_id)
    return await _grn_detail(db, grn)


@router.patch("/goods-receipts/{grn_id}", response_model=GoodsReceiptOut)
async def update_goods_receipt(
    grn_id: uuid.UUID, body: GoodsReceiptUpdate, _admin: AdminOnly, db: DB
) -> dict:
    grn = await _get_grn_or_404(db, grn_id)
    if grn.status != "draft":
        raise HTTPException(status_code=409, detail=f"goods receipt is {grn.status}; only drafts can be edited")

    update_data = body.model_dump(exclude_unset=True)
    old_values: dict = {}
    for field in ("receipt_date", "notes"):
        if field in update_data:
            old_values[field] = getattr(grn, field)
            setattr(grn, field, update_data[field])

    if "lines" in update_data and update_data["lines"] is not None:
        if not body.lines:
            raise HTTPException(status_code=422, detail="a goods receipt needs at least one line")
        for line_in in body.lines:
            await _get_item_or_422(db, line_in.item_id)
        if grn.po_id:
            po = await _get_po_or_404(db, grn.po_id)
            await _validate_grn_lines_against_po(db, po, body.lines, body.allow_over_receipt)
        existing = await _grn_lines(db, grn_id)
        old_values["lines"] = [{"item_id": line.item_id, "qty": line.qty} for line in existing]
        for line in existing:
            await db.delete(line)
        await db.flush()
        new_lines = [
            GoodsReceiptLine(
                grn=grn,
                po_line_id=line_in.po_line_id,
                item_id=line_in.item_id,
                qty=line_in.qty,
                unit_cost=line_in.unit_cost,
            )
            for line_in in body.lines
        ]
        db.add_all(new_lines)

    await db.commit()
    result = await db.execute(select(GoodsReceipt).where(GoodsReceipt.id == grn_id))
    grn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="goods_receipts",
        record_id=grn_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated goods receipt {grn.grn_no}",
    )
    return await _grn_detail(db, grn)


@router.delete("/goods-receipts/{grn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goods_receipt(grn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    grn = await _get_grn_or_404(db, grn_id)
    if grn.status != "draft":
        raise HTTPException(status_code=409, detail=f"goods receipt is {grn.status}; only drafts can be deleted")
    grn_no = grn.grn_no
    await db.delete(grn)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="goods_receipts",
        record_id=grn_id,
        description=f"Deleted draft goods receipt {grn_no}",
    )


async def _update_avg_cost(
    db: DB, item: InventoryItem, qty: int, unit_cost: float
) -> None:
    total_qty = await db.scalar(
        select(func.coalesce(func.sum(InventoryStock.quantity), 0)).where(
            InventoryStock.item_id == item.id
        )
    )
    total_qty = int(total_qty or 0)
    if total_qty + qty <= 0:
        return
    if total_qty == 0:
        item.avg_cost = unit_cost
    else:
        item.avg_cost = (
            Decimal(str(total_qty)) * Decimal(str(item.avg_cost))
            + Decimal(str(qty)) * Decimal(str(unit_cost))
        ) / Decimal(str(total_qty + qty))


@router.post("/goods-receipts/{grn_id}/confirm", response_model=GoodsReceiptOut)
async def confirm_goods_receipt(grn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    grn = await _get_grn_or_404(db, grn_id)
    if grn.status == "confirmed":
        return await _grn_detail(db, grn)
    if grn.status != "draft":
        raise HTTPException(status_code=409, detail=f"goods receipt is {grn.status}; cannot confirm")

    po = await _get_po_or_404(db, grn.po_id) if grn.po_id else None
    for line in await _grn_lines(db, grn_id):
        item = await _get_item_or_422(db, line.item_id)
        await _update_avg_cost(db, item, line.qty, float(line.unit_cost))
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=grn.location_id,
            type="in",
            quantity=line.qty,
            reason=f"GRN {grn.grn_no}",
            reason_code="other",
            reference=f"GRN:{grn.id}:{line.id}",
            user=_admin,
            item=item,
        )
        if line.po_line_id and po:
            po_line = await db.get(PurchaseOrderLine, line.po_line_id)
            if po_line:
                po_line.received_qty += line.qty
    if po:
        await _recompute_po_status(db, po)

    grn.status = "confirmed"
    await db.commit()
    result = await db.execute(select(GoodsReceipt).where(GoodsReceipt.id == grn_id))
    grn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="goods_receipts",
        record_id=grn_id,
        old_values={"status": "draft"},
        new_values={"status": "confirmed"},
        description=f"Confirmed goods receipt {grn.grn_no}",
    )
    return await _grn_detail(db, grn)


@router.post("/goods-receipts/{grn_id}/void", response_model=GoodsReceiptOut)
async def void_goods_receipt(grn_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    grn = await _get_grn_or_404(db, grn_id)
    if grn.status == "void":
        return await _grn_detail(db, grn)
    if grn.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"goods receipt is {grn.status}; cannot void")

    po = await _get_po_or_404(db, grn.po_id) if grn.po_id else None
    for line in await _grn_lines(db, grn_id):
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=grn.location_id,
            type="out",
            quantity=line.qty,
            reason=f"void GRN {grn.grn_no}",
            reason_code="other",
            reference=f"GRN-VOID:{grn.id}:{line.id}",
            user=_admin,
        )
        if line.po_line_id and po:
            po_line = await db.get(PurchaseOrderLine, line.po_line_id)
            if po_line:
                po_line.received_qty = max(0, po_line.received_qty - line.qty)
    if po:
        await _recompute_po_status(db, po)

    grn.status = "void"
    await db.commit()
    result = await db.execute(select(GoodsReceipt).where(GoodsReceipt.id == grn_id))
    grn = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="goods_receipts",
        record_id=grn_id,
        old_values={"status": "confirmed"},
        new_values={"status": "void"},
        description=f"Voided goods receipt {grn.grn_no}",
    )
    return await _grn_detail(db, grn)


# ---- Purchase returns ----


@router.get("/purchase-returns", response_model=list[PurchaseReturnOut])
async def list_purchase_returns(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    supplier_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    grn_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    clauses = []
    if supplier_id is not None:
        clauses.append(PurchaseReturn.supplier_id == supplier_id)
    if location_id is not None:
        clauses.append(PurchaseReturn.location_id == location_id)
    if grn_id is not None:
        clauses.append(PurchaseReturn.grn_id == grn_id)
    if status is not None:
        clauses.append(PurchaseReturn.status == status)

    count_q = select(func.count()).select_from(PurchaseReturn)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(PurchaseReturn)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(PurchaseReturn.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [await _prt_detail(db, prt) for prt in result.scalars().all()]


@router.post("/purchase-returns", response_model=PurchaseReturnOut, status_code=status.HTTP_201_CREATED)
async def create_purchase_return(body: PurchaseReturnCreate, _admin: AdminOnly, db: DB) -> dict:
    await _get_supplier_or_422(db, body.supplier_id)
    await _assert_location_exists(db, body.location_id)
    if not body.lines:
        raise HTTPException(status_code=422, detail="a purchase return needs at least one line")

    grn: GoodsReceipt | None = None
    if body.grn_id:
        grn = await _get_grn_or_404(db, body.grn_id)
        if grn.supplier_id != body.supplier_id or grn.location_id != body.location_id:
            raise HTTPException(status_code=422, detail="supplier_id/location_id must match the GRN")
        if grn.status != "confirmed":
            raise HTTPException(status_code=422, detail=f"GRN {grn.grn_no} is {grn.status}; cannot return against it")

    for line_in in body.lines:
        await _get_item_or_422(db, line_in.item_id)
    if grn:
        await _validate_return_qty(db, grn, body.lines)

    prt_no = await doc_numbers_svc.allocate_doc_no(db, location_id=body.location_id, doc_type="PRT")
    prt = PurchaseReturn(
        prt_no=prt_no,
        supplier_id=body.supplier_id,
        location_id=body.location_id,
        grn_id=body.grn_id,
        return_date=body.return_date,
        notes=body.notes,
        created_by=_admin.id,
    )
    db.add(prt)
    db.add_all(
        PurchaseReturnLine(prt=prt, item_id=l.item_id, qty=l.qty, unit_cost=l.unit_cost)
        for l in body.lines
    )
    await db.flush()
    prt_id = prt.id
    await db.commit()

    result = await db.execute(select(PurchaseReturn).where(PurchaseReturn.id == prt_id))
    prt = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="purchase_returns",
        record_id=prt.id,
        new_values={**body.model_dump(), "prt_no": prt_no},
        description=f"Created purchase return {prt_no}",
    )
    return await _prt_detail(db, prt)


async def _validate_return_qty(db: DB, grn: GoodsReceipt, line_inputs) -> None:
    received: dict[uuid.UUID, int] = {}
    for gl in await _grn_lines(db, grn.id):
        received[gl.item_id] = received.get(gl.item_id, 0) + gl.qty

    already_returned: dict[uuid.UUID, int] = {}
    other_returns = list(
        (
            await db.execute(
                select(PurchaseReturn.id).where(
                    PurchaseReturn.grn_id == grn.id, PurchaseReturn.status == "confirmed"
                )
            )
        ).scalars().all()
    )
    for prt_id in other_returns:
        for pl in await _prt_lines(db, prt_id):
            already_returned[pl.item_id] = already_returned.get(pl.item_id, 0) + pl.qty

    for line_in in line_inputs:
        cap = received.get(line_in.item_id, 0) - already_returned.get(line_in.item_id, 0)
        if line_in.qty > cap:
            raise HTTPException(
                status_code=422,
                detail=f"return qty {line_in.qty} exceeds returnable {cap} for item {line_in.item_id}",
            )


@router.get("/purchase-returns/{prt_id}", response_model=PurchaseReturnOut)
async def get_purchase_return(prt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    prt = await _get_prt_or_404(db, prt_id)
    return await _prt_detail(db, prt)


@router.patch("/purchase-returns/{prt_id}", response_model=PurchaseReturnOut)
async def update_purchase_return(
    prt_id: uuid.UUID, body: PurchaseReturnUpdate, _admin: AdminOnly, db: DB
) -> dict:
    prt = await _get_prt_or_404(db, prt_id)
    if prt.status != "draft":
        raise HTTPException(status_code=409, detail=f"purchase return is {prt.status}; only drafts can be edited")

    update_data = body.model_dump(exclude_unset=True)
    old_values: dict = {}
    if "grn_id" in update_data and update_data["grn_id"]:
        grn = await _get_grn_or_404(db, update_data["grn_id"])
        if grn.supplier_id != prt.supplier_id or grn.location_id != prt.location_id:
            raise HTTPException(status_code=422, detail="supplier/location must match the GRN")
    for field in ("grn_id", "return_date", "notes"):
        if field in update_data:
            old_values[field] = getattr(prt, field)
            setattr(prt, field, update_data[field])

    if "lines" in update_data and update_data["lines"] is not None:
        if not body.lines:
            raise HTTPException(status_code=422, detail="a purchase return needs at least one line")
        for line_in in body.lines:
            await _get_item_or_422(db, line_in.item_id)
        if prt.grn_id:
            grn = await _get_grn_or_404(db, prt.grn_id)
            await _validate_return_qty(db, grn, body.lines)
        existing = await _prt_lines(db, prt_id)
        old_values["lines"] = [{"item_id": line.item_id, "qty": line.qty} for line in existing]
        for line in existing:
            await db.delete(line)
        await db.flush()
        new_lines = [
            PurchaseReturnLine(prt=prt, item_id=l.item_id, qty=l.qty, unit_cost=l.unit_cost)
            for l in body.lines
        ]
        db.add_all(new_lines)

    await db.commit()
    result = await db.execute(select(PurchaseReturn).where(PurchaseReturn.id == prt_id))
    prt = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="purchase_returns",
        record_id=prt_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated purchase return {prt.prt_no}",
    )
    return await _prt_detail(db, prt)


@router.delete("/purchase-returns/{prt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_return(prt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    prt = await _get_prt_or_404(db, prt_id)
    if prt.status != "draft":
        raise HTTPException(status_code=409, detail=f"purchase return is {prt.status}; only drafts can be deleted")
    prt_no = prt.prt_no
    await db.delete(prt)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="purchase_returns",
        record_id=prt_id,
        description=f"Deleted draft purchase return {prt_no}",
    )


@router.post("/purchase-returns/{prt_id}/confirm", response_model=PurchaseReturnOut)
async def confirm_purchase_return(prt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    prt = await _get_prt_or_404(db, prt_id)
    if prt.status == "confirmed":
        return await _prt_detail(db, prt)
    if prt.status != "draft":
        raise HTTPException(status_code=409, detail=f"purchase return is {prt.status}; cannot confirm")

    prt_lines = await _prt_lines(db, prt_id)
    if prt.grn_id:
        grn = await _get_grn_or_404(db, prt.grn_id)
        if grn.status != "confirmed":
            raise HTTPException(status_code=422, detail=f"GRN {grn.grn_no} is {grn.status}; cannot return against it")
        await _validate_return_qty(db, grn, prt_lines)

    for line in prt_lines:
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=prt.location_id,
            type="out",
            quantity=line.qty,
            reason=f"purchase return {prt.prt_no}",
            reason_code="supplier_return",
            reference=f"PRT:{prt.id}:{line.id}",
            user=_admin,
        )

    prt.status = "confirmed"
    await db.commit()
    result = await db.execute(select(PurchaseReturn).where(PurchaseReturn.id == prt_id))
    prt = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="purchase_returns",
        record_id=prt_id,
        old_values={"status": "draft"},
        new_values={"status": "confirmed"},
        description=f"Confirmed purchase return {prt.prt_no}",
    )
    return await _prt_detail(db, prt)


@router.post("/purchase-returns/{prt_id}/void", response_model=PurchaseReturnOut)
async def void_purchase_return(prt_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    prt = await _get_prt_or_404(db, prt_id)
    if prt.status == "void":
        return await _prt_detail(db, prt)
    if prt.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"purchase return is {prt.status}; cannot void")

    for line in await _prt_lines(db, prt_id):
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=prt.location_id,
            type="in",
            quantity=line.qty,
            reason=f"void purchase return {prt.prt_no}",
            reason_code="other",
            reference=f"PRT-VOID:{prt.id}:{line.id}",
            user=_admin,
        )

    prt.status = "void"
    await db.commit()
    result = await db.execute(select(PurchaseReturn).where(PurchaseReturn.id == prt_id))
    prt = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="purchase_returns",
        record_id=prt_id,
        old_values={"status": "confirmed"},
        new_values={"status": "void"},
        description=f"Voided purchase return {prt.prt_no}",
    )
    return await _prt_detail(db, prt)
