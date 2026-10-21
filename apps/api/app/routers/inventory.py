import csv
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.inventory import (
    InventoryCategory,
    InventoryItem,
    InventoryMovement,
    InventoryStock,
    InventoryStocktake,
    InventoryStocktakeLine,
)
from app.models.location import Location
from app.schemas.inventory import (
    InventoryCategoryCreate,
    InventoryCategoryOut,
    InventoryCategoryUpdate,
    InventoryImportResult,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementOut,
    InventoryStockOut,
    InventoryStocktakeCreate,
    InventoryStocktakeDetailOut,
    InventoryStocktakeLinesPatch,
    InventoryStocktakeOut,
    InventoryTransferCreate,
    InventoryTransferOut,
)
from app.services import audit_log as audit_log_svc
from app.services import inventory as inventory_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def _assert_location_exists(db: DB, location_id: uuid.UUID) -> None:
    result = await db.execute(select(Location.id).where(Location.id == location_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")


async def _assert_category_exists(db: DB, category_id: uuid.UUID | None) -> None:
    if category_id is None:
        return
    result = await db.execute(select(InventoryCategory.id).where(InventoryCategory.id == category_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="category_id does not reference an existing category")


async def _get_item_or_404(db: DB, item_id: uuid.UUID) -> InventoryItem:
    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# ---- Categories ----


@router.get("/categories", response_model=list[InventoryCategoryOut])
async def list_inventory_categories(
    _admin: AdminOnly,
    db: DB,
    is_active: bool | None = None,
) -> list[InventoryCategory]:
    q = select(InventoryCategory)
    if is_active is not None:
        q = q.where(InventoryCategory.is_active == is_active)
    q = q.order_by(InventoryCategory.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/categories", response_model=InventoryCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_category(
    body: InventoryCategoryCreate, _admin: AdminOnly, db: DB
) -> InventoryCategory:
    category = InventoryCategory(**body.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_categories",
        record_id=category.id,
        new_values=body.model_dump(),
        description=f"Created inventory category {category.name_zh}",
    )
    return category


@router.patch("/categories/{category_id}", response_model=InventoryCategoryOut)
async def update_inventory_category(
    category_id: uuid.UUID, body: InventoryCategoryUpdate, _admin: AdminOnly, db: DB
) -> InventoryCategory:
    result = await db.execute(select(InventoryCategory).where(InventoryCategory.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    update_data = body.model_dump(exclude_unset=True)
    old_values = {field: getattr(category, field) for field in update_data}
    for field, value in update_data.items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_categories",
        record_id=category_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated inventory category {category.name_zh}",
    )
    return category


# ---- Items ----


@router.get("/items", response_model=list[InventoryItemOut])
async def list_inventory_items(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    low_stock: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryItem]:
    clauses = []
    if category_id is not None:
        clauses.append(InventoryItem.category_id == category_id)
    if is_active is not None:
        clauses.append(InventoryItem.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(InventoryItem.name_zh, search),
                ilike_contains(InventoryItem.name_en, search),
                ilike_contains(InventoryItem.sku_code, search),
            )
        )
    if low_stock:
        low_stock_exists = (
            select(InventoryStock.id)
            .where(
                InventoryStock.item_id == InventoryItem.id,
                InventoryStock.quantity <= InventoryItem.reorder_level,
            )
            .exists()
        )
        clauses.append(low_stock_exists)

    count_q = select(func.count()).select_from(InventoryItem)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(InventoryItem)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(InventoryItem.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("/items", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(body: InventoryItemCreate, _admin: AdminOnly, db: DB) -> InventoryItem:
    await _assert_category_exists(db, body.category_id)

    exists = await db.execute(select(InventoryItem).where(InventoryItem.sku_code == body.sku_code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="SKU code already exists")

    item = InventoryItem(**body.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_items",
        record_id=item.id,
        new_values=body.model_dump(),
        description=f"Created inventory item {item.sku_code} {item.name_zh}",
    )
    return item


@router.get("/items/{item_id}", response_model=InventoryItemOut)
async def get_inventory_item(item_id: uuid.UUID, _admin: AdminOnly, db: DB) -> InventoryItem:
    return await _get_item_or_404(db, item_id)


@router.patch("/items/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    item_id: uuid.UUID, body: InventoryItemUpdate, _admin: AdminOnly, db: DB
) -> InventoryItem:
    item = await _get_item_or_404(db, item_id)

    update_data = body.model_dump(exclude_unset=True)
    if "category_id" in update_data:
        await _assert_category_exists(db, update_data["category_id"])

    new_code = update_data.get("sku_code")
    if new_code:
        exists = await db.execute(
            select(InventoryItem).where(InventoryItem.sku_code == new_code, InventoryItem.id != item_id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="SKU code already exists")

    old_values = {field: getattr(item, field) for field in update_data}
    for field, value in update_data.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_items",
        record_id=item_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated inventory item {item.sku_code} {item.name_zh}",
    )
    return item


# ---- Stocks ----


@router.get("/stocks", response_model=list[InventoryStockOut])
async def list_inventory_stocks(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
) -> list[InventoryStock]:
    q = select(InventoryStock)
    if location_id is not None:
        q = q.where(InventoryStock.location_id == location_id)
    if item_id is not None:
        q = q.where(InventoryStock.item_id == item_id)
    result = await db.execute(q.order_by(InventoryStock.updated_at.desc()))
    return list(result.scalars().all())


@router.get("/low-stock", response_model=list[InventoryStockOut])
async def list_low_stock(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
) -> list[InventoryStock]:
    q = (
        select(InventoryStock)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .where(InventoryStock.quantity <= InventoryItem.reorder_level)
    )
    if location_id is not None:
        q = q.where(InventoryStock.location_id == location_id)
    result = await db.execute(q.order_by(InventoryStock.quantity.asc()))
    return list(result.scalars().all())


# ---- Movements ----


@router.post("/movements", response_model=InventoryMovementOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_movement(
    body: InventoryMovementCreate, _admin: AdminOnly, db: DB
) -> InventoryMovement:
    await _get_item_or_404(db, body.item_id)
    await _assert_location_exists(db, body.location_id)

    movement = await inventory_svc.apply_movement(
        db,
        item_id=body.item_id,
        location_id=body.location_id,
        type=body.type,
        quantity=body.quantity,
        reason=body.reason,
        reference=body.reference,
        user=_admin,
        reason_code=body.reason_code,
    )
    await db.commit()
    await db.refresh(movement)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_movements",
        record_id=movement.id,
        new_values={
            "item_id": body.item_id,
            "location_id": body.location_id,
            "type": body.type,
            "quantity": body.quantity,
            "quantity_delta": movement.quantity_delta,
            "balance_after": movement.balance_after,
            "reason": body.reason,
            "reason_code": body.reason_code,
            "reference": body.reference,
        },
        description=f"Inventory {movement.type} {movement.quantity_delta:+d} (balance {movement.balance_after})",
    )
    return movement


@router.get("/movements", response_model=list[InventoryMovementOut])
async def list_inventory_movements(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    item_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    type: str | None = None,
    reason_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryMovement]:
    clauses = []
    if item_id is not None:
        clauses.append(InventoryMovement.item_id == item_id)
    if location_id is not None:
        clauses.append(InventoryMovement.location_id == location_id)
    if type is not None:
        clauses.append(InventoryMovement.type == type)
    if reason_code is not None:
        clauses.append(InventoryMovement.reason_code == reason_code)
    if date_from is not None:
        clauses.append(InventoryMovement.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to is not None:
        clauses.append(
            InventoryMovement.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    count_q = select(func.count()).select_from(InventoryMovement)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(InventoryMovement)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(InventoryMovement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


# ---- Transfers ----


@router.post("/transfers", response_model=InventoryTransferOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_transfer(
    body: InventoryTransferCreate, _admin: AdminOnly, db: DB
) -> dict:
    await _get_item_or_404(db, body.item_id)
    await _assert_location_exists(db, body.from_location_id)
    await _assert_location_exists(db, body.to_location_id)

    out_movement, in_movement = await inventory_svc.transfer(
        db,
        item_id=body.item_id,
        from_location_id=body.from_location_id,
        to_location_id=body.to_location_id,
        quantity=body.quantity,
        reason=body.reason,
        user=_admin,
    )
    transfer_id = uuid.UUID(out_movement.reference.split(":")[1])
    await db.commit()
    await db.refresh(out_movement)
    await db.refresh(in_movement)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_movements",
        record_id=out_movement.id,
        new_values={
            "item_id": body.item_id,
            "from_location_id": body.from_location_id,
            "to_location_id": body.to_location_id,
            "quantity": body.quantity,
            "reason": body.reason,
        },
        description=f"Transferred {body.quantity} unit(s) of item {body.item_id}",
    )
    return {
        "transfer_id": transfer_id,
        "out_movement": out_movement,
        "in_movement": in_movement,
    }


# ---- Stocktakes ----


async def _get_stocktake_or_404(db: DB, stocktake_id: uuid.UUID) -> InventoryStocktake:
    result = await db.execute(
        select(InventoryStocktake).where(InventoryStocktake.id == stocktake_id)
    )
    stocktake = result.scalar_one_or_none()
    if not stocktake:
        raise HTTPException(status_code=404, detail="Stocktake not found")
    return stocktake


def _stocktake_detail(stocktake: InventoryStocktake, lines: list[InventoryStocktakeLine]) -> dict:
    return {
        **{f: getattr(stocktake, f) for f in InventoryStocktakeOut.model_fields},
        "lines": lines,
    }


@router.post(
    "/stocktakes", response_model=InventoryStocktakeDetailOut, status_code=status.HTTP_201_CREATED
)
async def create_inventory_stocktake(
    body: InventoryStocktakeCreate, _admin: AdminOnly, db: DB
) -> dict:
    await _assert_location_exists(db, body.location_id)

    items_q = select(InventoryItem).where(InventoryItem.is_active == True)  # noqa: E712
    if body.item_ids:
        items_q = items_q.where(InventoryItem.id.in_(body.item_ids))
    items = list((await db.execute(items_q)).scalars().all())
    if body.item_ids and len(items) != len(set(body.item_ids)):
        found = {i.id for i in items}
        missing = [str(i) for i in body.item_ids if i not in found]
        raise HTTPException(status_code=422, detail=f"unknown or inactive item_ids: {missing}")

    stocks = (
        await db.execute(
            select(InventoryStock).where(InventoryStock.location_id == body.location_id)
        )
    ).scalars().all()
    qty_by_item = {s.item_id: s.quantity for s in stocks}

    stocktake = InventoryStocktake(
        location_id=body.location_id, note=body.note, created_by=_admin.id
    )
    db.add(stocktake)
    lines = [
        InventoryStocktakeLine(
            stocktake=stocktake,
            item_id=item.id,
            system_qty=qty_by_item.get(item.id, 0),
        )
        for item in items
    ]
    db.add_all(lines)
    await db.commit()
    await db.refresh(stocktake)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_stocktakes",
        record_id=stocktake.id,
        new_values={
            "location_id": body.location_id,
            "item_count": len(lines),
            "note": body.note,
        },
        description=f"Created stocktake {stocktake.id} ({len(lines)} items)",
    )
    lines = list(
        (
            await db.execute(
                select(InventoryStocktakeLine)
                .where(InventoryStocktakeLine.stocktake_id == stocktake.id)
                .order_by(InventoryStocktakeLine.item_id)
            )
        ).scalars().all()
    )
    return _stocktake_detail(stocktake, lines)


@router.get("/stocktakes", response_model=list[InventoryStocktakeOut])
async def list_inventory_stocktakes(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    location_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryStocktake]:
    clauses = []
    if location_id is not None:
        clauses.append(InventoryStocktake.location_id == location_id)
    if status is not None:
        clauses.append(InventoryStocktake.status == status)

    count_q = select(func.count()).select_from(InventoryStocktake)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(InventoryStocktake)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(InventoryStocktake.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.get("/stocktakes/{stocktake_id}", response_model=InventoryStocktakeDetailOut)
async def get_inventory_stocktake(
    stocktake_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> dict:
    stocktake = await _get_stocktake_or_404(db, stocktake_id)
    lines = (
        await db.execute(
            select(InventoryStocktakeLine)
            .where(InventoryStocktakeLine.stocktake_id == stocktake_id)
            .order_by(InventoryStocktakeLine.item_id)
        )
    ).scalars().all()
    return _stocktake_detail(stocktake, list(lines))


@router.patch("/stocktakes/{stocktake_id}/lines", response_model=InventoryStocktakeDetailOut)
async def update_stocktake_lines(
    stocktake_id: uuid.UUID, body: InventoryStocktakeLinesPatch, _admin: AdminOnly, db: DB
) -> dict:
    stocktake = await _get_stocktake_or_404(db, stocktake_id)
    if stocktake.status != "draft":
        raise HTTPException(status_code=409, detail=f"stocktake is {stocktake.status}; cannot edit")

    lines = (
        await db.execute(
            select(InventoryStocktakeLine).where(InventoryStocktakeLine.stocktake_id == stocktake_id)
        )
    ).scalars().all()
    by_item = {line.item_id: line for line in lines}
    errors = []
    for update in body.lines:
        line = by_item.get(update.item_id)
        if line is None:
            errors.append(str(update.item_id))
        else:
            line.counted_qty = update.counted_qty
    if errors:
        raise HTTPException(status_code=422, detail=f"items not in this stocktake: {errors}")
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_stocktakes",
        record_id=stocktake_id,
        new_values={"lines": [l.model_dump() for l in body.lines]},
        description=f"Updated counts on stocktake {stocktake_id}",
    )
    lines = (
        await db.execute(
            select(InventoryStocktakeLine)
            .where(InventoryStocktakeLine.stocktake_id == stocktake_id)
            .order_by(InventoryStocktakeLine.item_id)
        )
    ).scalars().all()
    return _stocktake_detail(stocktake, list(lines))


@router.post("/stocktakes/{stocktake_id}/apply", response_model=InventoryStocktakeDetailOut)
async def apply_inventory_stocktake(
    stocktake_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> dict:
    stocktake = await _get_stocktake_or_404(db, stocktake_id)
    if stocktake.status == "applied":
        lines = (
            await db.execute(
                select(InventoryStocktakeLine)
                .where(InventoryStocktakeLine.stocktake_id == stocktake_id)
                .order_by(InventoryStocktakeLine.item_id)
            )
        ).scalars().all()
        return _stocktake_detail(stocktake, list(lines))
    if stocktake.status != "draft":
        raise HTTPException(status_code=409, detail=f"stocktake is {stocktake.status}")

    lines = (
        await db.execute(
            select(InventoryStocktakeLine).where(InventoryStocktakeLine.stocktake_id == stocktake_id)
        )
    ).scalars().all()
    applied_movements = 0
    for line in lines:
        if line.counted_qty is None or line.counted_qty == line.system_qty:
            continue
        reference = f"STK:{stocktake_id}:{line.item_id}"
        existing = await db.execute(
            select(InventoryMovement.id).where(InventoryMovement.reference == reference)
        )
        if existing.scalar_one_or_none():
            continue
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=stocktake.location_id,
            type="adjust",
            quantity=line.counted_qty,
            reason=stocktake.note or "stocktake",
            reference=reference,
            user=_admin,
        )
        applied_movements += 1

    stocktake.status = "applied"
    stocktake.applied_at = datetime.now(timezone.utc)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_stocktakes",
        record_id=stocktake_id,
        new_values={"status": "applied", "adjustments": applied_movements},
        description=f"Applied stocktake {stocktake_id} ({applied_movements} adjustments)",
    )
    lines = (
        await db.execute(
            select(InventoryStocktakeLine)
            .where(InventoryStocktakeLine.stocktake_id == stocktake_id)
            .order_by(InventoryStocktakeLine.item_id)
        )
    ).scalars().all()
    return _stocktake_detail(stocktake, list(lines))


@router.post("/stocktakes/{stocktake_id}/cancel", response_model=InventoryStocktakeOut)
async def cancel_inventory_stocktake(
    stocktake_id: uuid.UUID, _admin: AdminOnly, db: DB
) -> InventoryStocktake:
    stocktake = await _get_stocktake_or_404(db, stocktake_id)
    if stocktake.status != "draft":
        raise HTTPException(status_code=409, detail=f"stocktake is {stocktake.status}; cannot cancel")
    stocktake.status = "cancelled"
    await db.commit()
    await db.refresh(stocktake)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_stocktakes",
        record_id=stocktake_id,
        old_values={"status": "draft"},
        new_values={"status": "cancelled"},
        description=f"Cancelled stocktake {stocktake_id}",
    )
    return stocktake


# ---- CSV export ----


@router.get("/export/items.csv")
async def export_inventory_items(_admin: AdminOnly, db: DB) -> StreamingResponse:
    items = (
        await db.execute(select(InventoryItem).order_by(InventoryItem.sku_code))
    ).scalars().all()
    categories = (
        await db.execute(select(InventoryCategory))
    ).scalars().all()
    cat_name = {c.id: c.name_zh for c in categories}

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "sku_code",
        "name_zh",
        "name_en",
        "category",
        "unit_of_measure",
        "cost_price",
        "sale_price",
        "reorder_level",
        "is_active",
    ])
    for item in items:
        writer.writerow([
            item.sku_code,
            item.name_zh,
            item.name_en or "",
            cat_name.get(item.category_id, ""),
            item.unit_of_measure or "",
            item.cost_price if item.cost_price is not None else "",
            item.sale_price if item.sale_price is not None else "",
            item.reorder_level,
            item.is_active,
        ])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_items.csv"},
    )


@router.get("/export/stocks.csv")
async def export_inventory_stocks(
    _admin: AdminOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
) -> StreamingResponse:
    q = (
        select(InventoryStock, InventoryItem, Location)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .join(Location, Location.id == InventoryStock.location_id)
    )
    if location_id is not None:
        q = q.where(InventoryStock.location_id == location_id)
    q = q.order_by(Location.name_en, InventoryItem.sku_code)
    rows = (await db.execute(q)).all()

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "sku_code",
        "name_zh",
        "name_en",
        "location_code",
        "location",
        "quantity",
        "reserved",
        "available",
    ])
    for stock, item, location in rows:
        writer.writerow([
            item.sku_code,
            item.name_zh,
            item.name_en or "",
            location.code or "",
            location.name_en,
            stock.quantity,
            stock.reserved,
            stock.quantity - stock.reserved,
        ])
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_stocks.csv"},
    )


# ---- CSV import ----


async def _read_csv_rows(file: UploadFile) -> list[dict]:
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="empty or invalid CSV file")
    return [dict(row) for row in reader]


def _parse_decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"invalid number: {value}")


def _parse_int(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"invalid integer: {value}")


@router.post("/import/items", response_model=InventoryImportResult)
async def import_inventory_items(
    file: UploadFile, _admin: AdminOnly, db: DB
) -> InventoryImportResult:
    rows = await _read_csv_rows(file)

    categories = list((await db.execute(select(InventoryCategory))).scalars().all())
    cat_by_name = {c.name_zh.strip(): c for c in categories}
    cat_by_name.update(
        {c.name_en.strip(): c for c in categories if c.name_en}
    )
    existing_items = (
        await db.execute(select(InventoryItem))
    ).scalars().all()
    item_by_sku = {i.sku_code: i for i in existing_items}

    parsed = []
    errors = []
    for idx, row in enumerate(rows, start=2):
        sku = (row.get("sku_code") or "").strip()
        name_zh = (row.get("name_zh") or "").strip()
        if not sku or not name_zh:
            errors.append({"row": idx, "error": "sku_code and name_zh are required"})
            continue
        try:
            parsed.append(
                {
                    "row": idx,
                    "sku_code": sku,
                    "name_zh": name_zh,
                    "name_en": (row.get("name_en") or "").strip() or None,
                    "category": (row.get("category") or "").strip() or None,
                    "unit_of_measure": (row.get("unit_of_measure") or "").strip() or None,
                    "cost_price": _parse_decimal(row.get("cost_price")),
                    "sale_price": _parse_decimal(row.get("sale_price")),
                    "reorder_level": _parse_int(row.get("reorder_level")) or 0,
                }
            )
        except ValueError as exc:
            errors.append({"row": idx, "error": str(exc)})
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "CSV validation failed; nothing was imported", "errors": errors},
        )

    created = updated = 0
    for row in parsed:
        category_id = None
        if row["category"]:
            category = cat_by_name.get(row["category"])
            if category is None:
                category = InventoryCategory(id=uuid.uuid4(), name_zh=row["category"])
                db.add(category)
                cat_by_name[row["category"]] = category
            category_id = category.id

        item = item_by_sku.get(row["sku_code"])
        if item is None:
            item = InventoryItem(
                sku_code=row["sku_code"],
                name_zh=row["name_zh"],
                name_en=row["name_en"],
                category_id=category_id,
                unit_of_measure=row["unit_of_measure"],
                cost_price=row["cost_price"],
                sale_price=row["sale_price"],
                reorder_level=row["reorder_level"],
            )
            db.add(item)
            created += 1
        else:
            item.name_zh = row["name_zh"]
            item.name_en = row["name_en"]
            item.category_id = category_id
            item.unit_of_measure = row["unit_of_measure"]
            item.cost_price = row["cost_price"]
            item.sale_price = row["sale_price"]
            item.reorder_level = row["reorder_level"]
            updated += 1
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_items",
        new_values={"imported_created": created, "imported_updated": updated},
        description=f"Imported items CSV: {created} created, {updated} updated",
    )
    return InventoryImportResult(created=created, updated=updated)


@router.post("/import/opening-stock", response_model=InventoryImportResult)
async def import_opening_stock(
    file: UploadFile, _admin: AdminOnly, db: DB
) -> InventoryImportResult:
    rows = await _read_csv_rows(file)

    items = (await db.execute(select(InventoryItem))).scalars().all()
    item_by_sku = {i.sku_code: i for i in items}
    locations = (await db.execute(select(Location))).scalars().all()
    loc_by_key: dict[str, Location] = {}
    for loc in locations:
        loc_by_key[str(loc.id)] = loc
        if loc.code:
            loc_by_key[loc.code] = loc

    parsed = []
    errors = []
    for idx, row in enumerate(rows, start=2):
        sku = (row.get("sku_code") or "").strip()
        loc_key = (
            (row.get("location") or row.get("location_code") or row.get("location_id") or "").strip()
        )
        try:
            quantity = _parse_int(row.get("quantity"))
        except ValueError as exc:
            errors.append({"row": idx, "error": str(exc)})
            continue
        if sku not in item_by_sku:
            errors.append({"row": idx, "error": f"unknown sku_code: {sku}"})
            continue
        if loc_key not in loc_by_key:
            errors.append({"row": idx, "error": f"unknown location: {loc_key}"})
            continue
        if quantity is None or quantity < 0:
            errors.append({"row": idx, "error": "quantity must be a non-negative integer"})
            continue
        parsed.append(
            {
                "row": idx,
                "item": item_by_sku[sku],
                "location": loc_by_key[loc_key],
                "quantity": quantity,
            }
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "CSV validation failed; nothing was imported", "errors": errors},
        )

    created = skipped = 0
    for row in parsed:
        item = row["item"]
        location = row["location"]
        reference = f"OPEN:{location.id}:{item.sku_code}"
        existing = await db.execute(
            select(InventoryMovement.id).where(InventoryMovement.reference == reference)
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        await inventory_svc.apply_movement(
            db,
            item_id=item.id,
            location_id=location.id,
            type="in",
            quantity=row["quantity"],
            reason="opening stock import",
            reason_code="opening",
            reference=reference,
            user=_admin,
            item=item,
        )
        created += 1
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_movements",
        new_values={"opening_created": created, "opening_skipped": skipped},
        description=f"Imported opening stock CSV: {created} movements, {skipped} skipped",
    )
    return InventoryImportResult(created=created, skipped=skipped)
