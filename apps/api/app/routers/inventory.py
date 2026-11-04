import csv
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.attendance_tz import ATTENDANCE_TZ
from app.deps import AdminOnly, DB
from app.models.inventory import (
    InventoryCategory,
    InventoryItem,
    InventoryWarehouse,
    InventoryMovement,
    InventoryStock,
    InventoryStocktake,
    InventoryStocktakeLine,
)
from app.models.inventory_invoicing import InventoryCreditNote, InventoryInvoice, InventoryReceipt
from app.models.inventory_purchasing import GoodsReceipt, InventoryCounter, PurchaseOrder, PurchaseReturn
from app.models.inventory_sales import DeliveryOrder, SalesOrder
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
    InventoryWarehouseCreate,
    InventoryWarehouseOut,
    InventoryWarehouseUpdate,
)
from app.services import audit_log as audit_log_svc
from app.services import inventory as inventory_svc
from app.utils import csv_export
from app.utils.search import ilike_contains

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def _assert_warehouse_exists(db: DB, warehouse_id: uuid.UUID) -> None:
    result = await db.execute(select(InventoryWarehouse).where(InventoryWarehouse.id == warehouse_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=422, detail="warehouse_id does not reference an existing warehouse")
    if not location.is_active:
        raise HTTPException(status_code=422, detail=f"warehouse {location.name_en or location.name_zh} is inactive")


async def _assert_item_active(db: DB, item_id: uuid.UUID) -> InventoryItem:
    item = await _get_item_or_404(db, item_id)
    if not item.is_active:
        raise HTTPException(status_code=422, detail=f"item {item.sku_code} is inactive")
    return item


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


async def _assert_centre_exists(db: DB, location_id: uuid.UUID | None) -> None:
    if location_id is None:
        return
    result = await db.execute(select(Location.id).where(Location.id == location_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="location_id does not reference an existing centre")


_WAREHOUSE_REF_COLUMNS = (
    InventoryStock.warehouse_id,
    InventoryMovement.warehouse_id,
    InventoryStocktake.warehouse_id,
    InventoryCounter.warehouse_id,
    PurchaseOrder.warehouse_id,
    GoodsReceipt.warehouse_id,
    PurchaseReturn.warehouse_id,
    SalesOrder.warehouse_id,
    DeliveryOrder.warehouse_id,
    InventoryInvoice.warehouse_id,
    InventoryReceipt.warehouse_id,
    InventoryCreditNote.warehouse_id,
)


async def _warehouse_is_referenced(db: DB, warehouse_id: uuid.UUID) -> bool:
    for column in _WAREHOUSE_REF_COLUMNS:
        hit = await db.scalar(select(column).where(column == warehouse_id).limit(1))
        if hit is not None:
            return True
    return False


# ---- Warehouses ----


@router.get("/warehouses", response_model=list[InventoryWarehouseOut])
async def list_warehouses(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryWarehouse]:
    clauses = []
    if is_active is not None:
        clauses.append(InventoryWarehouse.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(InventoryWarehouse.code, search),
                ilike_contains(InventoryWarehouse.name_zh, search),
                ilike_contains(InventoryWarehouse.name_en, search),
            )
        )
    count_q = select(func.count()).select_from(InventoryWarehouse)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0
    q = select(InventoryWarehouse)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(InventoryWarehouse.code).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("/warehouses", response_model=InventoryWarehouseOut, status_code=status.HTTP_201_CREATED)
async def create_warehouse(body: InventoryWarehouseCreate, _admin: AdminOnly, db: DB) -> InventoryWarehouse:
    exists = await db.execute(select(InventoryWarehouse.id).where(InventoryWarehouse.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Warehouse code already exists")
    await _assert_centre_exists(db, body.location_id)
    warehouse = InventoryWarehouse(**body.model_dump())
    db.add(warehouse)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Warehouse code already exists")
    await db.commit()
    await db.refresh(warehouse)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_warehouses",
        record_id=warehouse.id,
        new_values=body.model_dump(mode="json"),
        description=f"Created warehouse {warehouse.code} {warehouse.name_zh}",
    )
    return warehouse


@router.patch("/warehouses/{warehouse_id}", response_model=InventoryWarehouseOut)
async def update_warehouse(
    warehouse_id: uuid.UUID, body: InventoryWarehouseUpdate, _admin: AdminOnly, db: DB
) -> InventoryWarehouse:
    warehouse = await db.get(InventoryWarehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    update_data = body.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(
            select(InventoryWarehouse.id).where(
                InventoryWarehouse.code == new_code, InventoryWarehouse.id != warehouse_id
            )
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Warehouse code already exists")
    if "location_id" in update_data:
        await _assert_centre_exists(db, update_data["location_id"])
    old_values = {field: getattr(warehouse, field) for field in update_data}
    for field, value in update_data.items():
        setattr(warehouse, field, value)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Warehouse code already exists")
    await db.commit()
    await db.refresh(warehouse)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_warehouses",
        record_id=warehouse.id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated warehouse {warehouse.code}",
    )
    return warehouse


@router.delete("/warehouses/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse(warehouse_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    warehouse = await db.get(InventoryWarehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    if await _warehouse_is_referenced(db, warehouse_id):
        raise HTTPException(
            status_code=409,
            detail="Warehouse is referenced by stock or documents; deactivate it instead",
        )
    code = warehouse.code
    await db.delete(warehouse)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="inventory_warehouses",
        record_id=warehouse_id,
        description=f"Deleted warehouse {code}",
    )


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
                ilike_contains(InventoryItem.barcode, search),
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
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="SKU code already exists")
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
    warehouse_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
) -> list[InventoryStock]:
    q = select(InventoryStock)
    if warehouse_id is not None:
        q = q.where(InventoryStock.warehouse_id == warehouse_id)
    if item_id is not None:
        q = q.where(InventoryStock.item_id == item_id)
    result = await db.execute(q.order_by(InventoryStock.updated_at.desc()))
    return list(result.scalars().all())


@router.get("/low-stock", response_model=list[InventoryStockOut])
async def list_low_stock(
    _admin: AdminOnly,
    db: DB,
    warehouse_id: uuid.UUID | None = None,
) -> list[InventoryStock]:
    q = (
        select(InventoryStock)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .where(InventoryStock.quantity <= InventoryItem.reorder_level)
    )
    if warehouse_id is not None:
        q = q.where(InventoryStock.warehouse_id == warehouse_id)
    result = await db.execute(q.order_by(InventoryStock.quantity.asc()))
    return list(result.scalars().all())


# ---- Movements ----


@router.post("/movements", response_model=InventoryMovementOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_movement(
    body: InventoryMovementCreate, _admin: AdminOnly, db: DB, response: Response
) -> InventoryMovement:
    await _assert_item_active(db, body.item_id)
    await _assert_warehouse_exists(db, body.warehouse_id)

    if body.reference:
        existing = (
            await db.execute(
                select(InventoryMovement).where(InventoryMovement.reference == body.reference)
            )
        ).scalar_one_or_none()
        if existing is not None:
            # Idempotent repeat — return the recorded movement as 200, no audit.
            if (
                existing.item_id != body.item_id
                or existing.warehouse_id != body.warehouse_id
                or existing.type != body.type
            ):
                raise HTTPException(
                    status_code=409, detail="reference already used by a different movement"
                )
            response.status_code = status.HTTP_200_OK
            return existing

    movement = await inventory_svc.apply_movement(
        db,
        item_id=body.item_id,
        warehouse_id=body.warehouse_id,
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
            "warehouse_id": body.warehouse_id,
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
    warehouse_id: uuid.UUID | None = None,
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
    if warehouse_id is not None:
        clauses.append(InventoryMovement.warehouse_id == warehouse_id)
    if type is not None:
        clauses.append(InventoryMovement.type == type)
    if reason_code is not None:
        clauses.append(InventoryMovement.reason_code == reason_code)
    if date_from is not None:
        clauses.append(InventoryMovement.created_at >= datetime.combine(date_from, time.min, tzinfo=ATTENDANCE_TZ))
    if date_to is not None:
        clauses.append(
            InventoryMovement.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=ATTENDANCE_TZ)
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
    await _assert_item_active(db, body.item_id)
    await _assert_warehouse_exists(db, body.from_warehouse_id)
    await _assert_warehouse_exists(db, body.to_warehouse_id)

    out_movement, in_movement = await inventory_svc.transfer(
        db,
        item_id=body.item_id,
        from_warehouse_id=body.from_warehouse_id,
        to_warehouse_id=body.to_warehouse_id,
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
            "from_warehouse_id": body.from_warehouse_id,
            "to_warehouse_id": body.to_warehouse_id,
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
    await _assert_warehouse_exists(db, body.warehouse_id)

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
            select(InventoryStock).where(InventoryStock.warehouse_id == body.warehouse_id)
        )
    ).scalars().all()
    qty_by_item = {s.item_id: s.quantity for s in stocks}

    stocktake = InventoryStocktake(
        warehouse_id=body.warehouse_id, note=body.note, created_by=_admin.id
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
            "warehouse_id": body.warehouse_id,
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
    warehouse_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryStocktake]:
    clauses = []
    if warehouse_id is not None:
        clauses.append(InventoryStocktake.warehouse_id == warehouse_id)
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
    stocktake = (
        await db.execute(
            select(InventoryStocktake)
            .where(InventoryStocktake.id == stocktake_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if stocktake is None:
        raise HTTPException(status_code=404, detail="Stocktake not found")
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
        if line.counted_qty is None:
            continue
        delta = line.counted_qty - line.system_qty
        if delta == 0:
            continue
        reference = f"STK:{stocktake_id}:{line.item_id}"
        existing = await db.execute(
            select(InventoryMovement.id).where(InventoryMovement.reference == reference)
        )
        if existing.scalar_one_or_none():
            continue
        await _assert_item_active(db, line.item_id)
        await inventory_svc.adjust_by(
            db,
            item_id=line.item_id,
            warehouse_id=stocktake.warehouse_id,
            delta=delta,
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
    stocktake = (
        await db.execute(
            select(InventoryStocktake)
            .where(InventoryStocktake.id == stocktake_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if stocktake is None:
        raise HTTPException(status_code=404, detail="Stocktake not found")
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
async def export_inventory_items(_admin: AdminOnly, db: DB) -> Response:
    items = (
        await db.execute(select(InventoryItem).order_by(InventoryItem.sku_code))
    ).scalars().all()
    categories = (
        await db.execute(select(InventoryCategory))
    ).scalars().all()
    cat_name = {c.id: c.name_zh for c in categories}

    rows = [
        [
            item.sku_code,
            item.name_zh,
            item.name_en or "",
            cat_name.get(item.category_id, ""),
            item.unit_of_measure or "",
            item.barcode or "",
            item.cost_price if item.cost_price is not None else "",
            item.other_cost if item.other_cost is not None else "",
            item.sale_price if item.sale_price is not None else "",
            item.reorder_level,
            item.is_active,
        ]
        for item in items
    ]
    return csv_export.csv_response(
        "inventory_items.csv",
        [
            "sku_code",
            "name_zh",
            "name_en",
            "category",
            "unit_of_measure",
            "barcode",
            "cost_price",
            "other_cost",
            "sale_price",
            "reorder_level",
            "is_active",
        ],
        rows,
    )


@router.get("/export/stocks.csv")
async def export_inventory_stocks(
    _admin: AdminOnly,
    db: DB,
    warehouse_id: uuid.UUID | None = None,
) -> Response:
    q = (
        select(InventoryStock, InventoryItem, InventoryWarehouse)
        .join(InventoryItem, InventoryItem.id == InventoryStock.item_id)
        .join(InventoryWarehouse, InventoryWarehouse.id == InventoryStock.warehouse_id)
    )
    if warehouse_id is not None:
        q = q.where(InventoryStock.warehouse_id == warehouse_id)
    q = q.order_by(InventoryWarehouse.code, InventoryItem.sku_code)
    rows_raw = (await db.execute(q)).all()

    rows = [
        [
            item.sku_code,
            item.name_zh,
            item.name_en or "",
            location.code or "",
            location.name_en or location.name_zh,
            stock.quantity,
            stock.reserved,
            stock.quantity - stock.reserved,
        ]
        for stock, item, location in rows_raw
    ]
    return csv_export.csv_response(
        "inventory_stocks.csv",
        [
            "sku_code",
            "name_zh",
            "name_en",
            "warehouse_code",
            "warehouse",
            "quantity",
            "reserved",
            "available",
        ],
        rows,
    )


# ---- CSV import ----


CSV_MAX_BYTES = 5 * 1024 * 1024


async def _read_csv_rows(file: UploadFile) -> list[dict]:
    raw_bytes = await file.read()
    if len(raw_bytes) > CSV_MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds the 5 MB limit")
    raw = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="empty or invalid CSV file")
    return [dict(row) for row in reader]


def _parse_decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"invalid number: {value}")
    if not parsed.is_finite():
        raise ValueError(f"invalid number: {value}")
    return parsed


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
            cost_price = _parse_decimal(row.get("cost_price"))
            other_cost = _parse_decimal(row.get("other_cost"))
            sale_price = _parse_decimal(row.get("sale_price"))
            reorder_level = _parse_int(row.get("reorder_level"))
            if cost_price is not None and cost_price < 0:
                raise ValueError("cost_price must be >= 0")
            if other_cost is not None and other_cost < 0:
                raise ValueError("other_cost must be >= 0")
            if sale_price is not None and sale_price < 0:
                raise ValueError("sale_price must be >= 0")
            if reorder_level is not None and reorder_level < 0:
                raise ValueError("reorder_level must be >= 0")
            barcode = (row.get("barcode") or "").strip() or None
            if barcode is not None and len(barcode) > 100:
                raise ValueError("barcode must be <= 100 characters")
            parsed.append(
                {
                    "row": idx,
                    "sku_code": sku,
                    "name_zh": name_zh,
                    "name_en": (row.get("name_en") or "").strip() or None,
                    "category": (row.get("category") or "").strip() or None,
                    "unit_of_measure": (row.get("unit_of_measure") or "").strip() or None,
                    "has_barcode": "barcode" in row,
                    "has_other_cost": "other_cost" in row,
                    "barcode": barcode,
                    "cost_price": cost_price,
                    "other_cost": other_cost,
                    "sale_price": sale_price,
                    "reorder_level": reorder_level if reorder_level is not None else 0,
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
                barcode=row["barcode"],
                cost_price=row["cost_price"],
                other_cost=row["other_cost"],
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
            if row["has_barcode"]:
                item.barcode = row["barcode"]
            item.cost_price = row["cost_price"]
            if row["has_other_cost"]:
                item.other_cost = row["other_cost"]
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
    locations = (await db.execute(select(InventoryWarehouse))).scalars().all()
    loc_by_key: dict[str, InventoryWarehouse] = {}
    for loc in locations:
        loc_by_key[str(loc.id)] = loc
        if loc.code:
            loc_by_key[loc.code] = loc

    parsed = []
    errors = []
    for idx, row in enumerate(rows, start=2):
        sku = (row.get("sku_code") or "").strip()
        loc_key = (
            (
                row.get("warehouse") or row.get("warehouse_code") or row.get("warehouse_id")
                or row.get("location") or row.get("location_code") or ""
            ).strip()
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
            errors.append({"row": idx, "error": f"unknown warehouse: {loc_key}"})
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
        if row["quantity"] == 0:
            skipped += 1
            continue
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
            warehouse_id=location.id,
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
