import csv
import itertools
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.attendance_tz import ATTENDANCE_TZ
from app.deps import AdminOnly, DB
from app.models.inventory import (
    InventoryBrand,
    InventoryCategory,
    InventoryItem,
    InventoryProduct,
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
    InventoryBrandCreate,
    InventoryBrandOut,
    InventoryBrandUpdate,
    InventoryCategoryCreate,
    InventoryCategoryOut,
    InventoryCategoryUpdate,
    InventoryGenerateSkusRequest,
    InventoryImportResult,
    InventoryItemCreate,
    InventoryItemOut,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementOut,
    InventoryProductCreate,
    InventoryProductOut,
    InventoryProductSkuInput,
    InventoryProductUpdate,
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


async def _load_product(db: DB, product_id: uuid.UUID) -> InventoryProduct | None:
    result = await db.execute(
        select(InventoryProduct)
        .where(InventoryProduct.id == product_id)
        .options(selectinload(InventoryProduct.skus))
        .execution_options(populate_existing=True)
    )
    product = result.scalar_one_or_none()
    if product is not None:
        await _attach_on_hand(db, list(product.skus))
    return product


async def _get_product_or_404(db: DB, product_id: uuid.UUID) -> InventoryProduct:
    product = await _load_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


async def _validate_item_variant(
    db: DB,
    product_id: uuid.UUID | None,
    variant_attrs: dict | None,
    exclude_item_id: uuid.UUID | None = None,
) -> None:
    if product_id is None:
        if variant_attrs:
            raise HTTPException(status_code=422, detail="variant_attrs requires a product_id")
        return
    product = await _load_product(db, product_id)
    if not product:
        raise HTTPException(status_code=422, detail="product_id does not reference an existing product")
    if not variant_attrs:
        return
    options = product.options or {}
    if options:
        for key, value in variant_attrs.items():
            if key not in options:
                raise HTTPException(
                    status_code=422, detail=f"variant_attrs key '{key}' is not an option of this product"
                )
            if value not in options[key]:
                raise HTTPException(
                    status_code=422, detail=f"variant_attrs value '{value}' is not allowed for option '{key}'"
                )
    for sibling in product.skus:
        if sibling.id != exclude_item_id and sibling.variant_attrs == variant_attrs:
            raise HTTPException(
                status_code=409,
                detail=f"Another SKU of this product already uses these variant_attrs ({sibling.sku_code})",
            )


async def _assert_brand_exists(db: DB, brand_id: uuid.UUID | None) -> None:
    if brand_id is None:
        return
    result = await db.execute(select(InventoryBrand.id).where(InventoryBrand.id == brand_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="brand_id does not reference an existing brand")


def _category_ids_with_children(category_id: uuid.UUID):
    return select(InventoryCategory.id).where(
        or_(InventoryCategory.id == category_id, InventoryCategory.parent_id == category_id)
    )


async def _attach_on_hand(db: DB, items: list[InventoryItem]) -> None:
    totals: dict[uuid.UUID, int] = {}
    ids = [item.id for item in items]
    for start in range(0, len(ids), 5000):
        rows = await db.execute(
            select(InventoryStock.item_id, func.coalesce(func.sum(InventoryStock.quantity), 0))
            .where(InventoryStock.item_id.in_(ids[start : start + 5000]))
            .group_by(InventoryStock.item_id)
        )
        totals.update({item_id: int(total) for item_id, total in rows.all()})
    for item in items:
        item.on_hand = totals.get(item.id, 0)


async def _assert_product_active_for_item(db: DB, product_id: uuid.UUID | None, is_active: bool | None) -> None:
    if product_id is None or not is_active:
        return
    product = await db.get(InventoryProduct, product_id)
    if product is not None and not product.is_active:
        raise HTTPException(status_code=409, detail="Product is inactive")


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


async def _validate_category_tree(
    db: DB,
    *,
    category_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
    name_zh: str,
    check_parent: bool,
) -> None:
    if parent_id is not None and check_parent:
        if category_id is not None and parent_id == category_id:
            raise HTTPException(status_code=422, detail="A category cannot be its own parent")
        parent = await db.get(InventoryCategory, parent_id)
        if parent is None:
            raise HTTPException(status_code=422, detail="parent_id does not reference an existing category")
        if parent.parent_id is not None:
            raise HTTPException(status_code=422, detail="Only 2 levels allowed")
        if category_id is not None:
            has_children = await db.scalar(
                select(InventoryCategory.id).where(InventoryCategory.parent_id == category_id).limit(1)
            )
            if has_children is not None:
                raise HTTPException(
                    status_code=422, detail="A category that has sub-categories cannot be given a parent"
                )
    dup_q = select(InventoryCategory.id).where(
        func.lower(func.trim(InventoryCategory.name_zh)) == name_zh.strip().lower(),
        InventoryCategory.parent_id.is_(None) if parent_id is None else InventoryCategory.parent_id == parent_id,
    )
    if category_id is not None:
        dup_q = dup_q.where(InventoryCategory.id != category_id)
    if (await db.scalar(dup_q.limit(1))) is not None:
        raise HTTPException(status_code=409, detail="Category name already exists at this level")


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
    await _validate_category_tree(
        db, category_id=None, parent_id=body.parent_id, name_zh=body.name_zh, check_parent=True
    )
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
        new_values=body.model_dump(mode="json"),
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
    if update_data.get("name_zh", "") is None:
        raise HTTPException(status_code=422, detail="name_zh must not be null")
    if update_data.get("is_active", True) is None:
        raise HTTPException(status_code=422, detail="is_active must not be null")
    if "name_zh" in update_data or "parent_id" in update_data:
        await _validate_category_tree(
            db,
            category_id=category_id,
            parent_id=update_data.get("parent_id", category.parent_id),
            name_zh=update_data.get("name_zh", category.name_zh),
            check_parent="parent_id" in update_data,
        )
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


# ---- Brands ----


async def _assert_brand_name_free(db: DB, name_zh: str, exclude_id: uuid.UUID | None = None) -> None:
    q = select(InventoryBrand.id).where(func.lower(func.trim(InventoryBrand.name_zh)) == name_zh.strip().lower())
    if exclude_id is not None:
        q = q.where(InventoryBrand.id != exclude_id)
    if (await db.scalar(q.limit(1))) is not None:
        raise HTTPException(status_code=409, detail="Brand name already exists")


@router.get("/brands", response_model=list[InventoryBrandOut])
async def list_inventory_brands(
    _admin: AdminOnly,
    db: DB,
    is_active: bool | None = None,
) -> list[InventoryBrand]:
    q = select(InventoryBrand)
    if is_active is not None:
        q = q.where(InventoryBrand.is_active == is_active)
    q = q.order_by(InventoryBrand.name_zh)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/brands", response_model=InventoryBrandOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_brand(body: InventoryBrandCreate, _admin: AdminOnly, db: DB) -> InventoryBrand:
    await _assert_brand_name_free(db, body.name_zh)
    brand = InventoryBrand(**body.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_brands",
        record_id=brand.id,
        new_values=body.model_dump(mode="json"),
        description=f"Created inventory brand {brand.name_zh}",
    )
    return brand


@router.patch("/brands/{brand_id}", response_model=InventoryBrandOut)
async def update_inventory_brand(
    brand_id: uuid.UUID, body: InventoryBrandUpdate, _admin: AdminOnly, db: DB
) -> InventoryBrand:
    brand = await db.get(InventoryBrand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    update_data = body.model_dump(exclude_unset=True)
    for required in ("name_zh", "is_active"):
        if required in update_data and update_data[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} must not be null")
    if "name_zh" in update_data:
        await _assert_brand_name_free(db, update_data["name_zh"], exclude_id=brand_id)
    old_values = {field: getattr(brand, field) for field in update_data}
    for field, value in update_data.items():
        setattr(brand, field, value)
    await db.commit()
    await db.refresh(brand)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_brands",
        record_id=brand_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated inventory brand {brand.name_zh}",
    )
    return brand


# ---- Products ----


def _assert_options_cover_skus(options: dict | None, skus: list[InventoryItem]) -> None:
    for sku in skus:
        for key, value in (sku.variant_attrs or {}).items():
            if options is None or key not in options or value not in options[key]:
                raise HTTPException(
                    status_code=409,
                    detail=f"Option '{key}: {value}' is used by SKU {sku.sku_code} and cannot be removed",
                )


@router.get("/products", response_model=list[InventoryProductOut])
async def list_inventory_products(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    category_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryProduct]:
    clauses = []
    if category_id is not None:
        clauses.append(InventoryProduct.category_id.in_(_category_ids_with_children(category_id)))
    if brand_id is not None:
        clauses.append(InventoryProduct.brand_id == brand_id)
    if is_active is not None:
        clauses.append(InventoryProduct.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(InventoryProduct.code, search),
                ilike_contains(InventoryProduct.name_zh, search),
                ilike_contains(InventoryProduct.name_en, search),
            )
        )
    count_q = select(func.count()).select_from(InventoryProduct)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(InventoryProduct).options(selectinload(InventoryProduct.skus))
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(InventoryProduct.code).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    products = list(result.scalars().all())
    await _attach_on_hand(db, [sku for product in products for sku in product.skus])
    return products


def _set_sku_names(product: InventoryProduct, sku: InventoryItem) -> None:
    values = list((sku.variant_attrs or {}).values())
    suffix = f" {' / '.join(values)}" if values else ""
    name_zh = f"{product.name_zh}{suffix}"
    name_en = f"{product.name_en}{suffix}" if product.name_en else None
    if len(name_zh) > 255 or (name_en is not None and len(name_en) > 255):
        raise HTTPException(status_code=422, detail=f"Derived name for SKU is longer than 255 characters: {name_zh}")
    sku.name_zh = name_zh
    sku.name_en = name_en


def _deactivate_skus_of_inactive_product(product: InventoryProduct) -> list[str]:
    if product.is_active:
        return []
    deactivated = []
    for sku in product.skus:
        if sku.is_active:
            sku.is_active = False
            deactivated.append(sku.sku_code)
    return deactivated


def _validate_product_skus(product: InventoryProduct) -> None:
    options = product.options or {}
    keys = set(options)
    seen: dict[tuple, str] = {}
    for sku in product.skus:
        attrs = sku.variant_attrs
        if not attrs:
            continue
        if set(attrs) != keys:
            raise HTTPException(
                status_code=422,
                detail=f"SKU {sku.sku_code} must have a value for exactly these option(s): {', '.join(options)}",
            )
        for key, value in attrs.items():
            if value not in options[key]:
                raise HTTPException(
                    status_code=422,
                    detail=f"SKU {sku.sku_code}: '{value}' is not an allowed value for option '{key}'",
                )
        signature = tuple(sorted(attrs.items()))
        if signature in seen:
            raise HTTPException(
                status_code=409,
                detail=f"SKUs {seen[signature]} and {sku.sku_code} have the same variant_attrs",
            )
        seen[signature] = sku.sku_code


async def _apply_sku_inputs(
    db: DB, product: InventoryProduct, entries: list[InventoryProductSkuInput]
) -> tuple[list[str], list[str]]:
    if not product.options:
        raise HTTPException(status_code=422, detail="options are required when skus are given")
    by_id = {sku.id: sku for sku in product.skus}
    payload_ids = [entry.id for entry in entries if entry.id is not None]
    if len(set(payload_ids)) != len(payload_ids):
        raise HTTPException(status_code=422, detail="Duplicate SKU id in skus")
    for entry_id in payload_ids:
        if entry_id not in by_id:
            raise HTTPException(status_code=422, detail=f"SKU {entry_id} does not belong to this product")

    codes = [entry.sku_code for entry in entries]
    duplicated = sorted({code for code in codes if codes.count(code) > 1})
    if duplicated:
        raise HTTPException(status_code=409, detail=f"Duplicate sku_code in payload: {', '.join(duplicated)}")
    if codes:
        taken_q = select(InventoryItem.sku_code).where(InventoryItem.sku_code.in_(codes))
        if payload_ids:
            taken_q = taken_q.where(InventoryItem.id.not_in(payload_ids))
        taken = sorted((await db.execute(taken_q)).scalars().all())
        if taken:
            raise HTTPException(status_code=409, detail=f"SKU code already exists: {', '.join(taken)}")

    created: list[str] = []
    updated: list[str] = []
    for entry in entries:
        if entry.id is not None:
            sku = by_id[entry.id]
            updated.append(entry.sku_code)
        else:
            sku = InventoryItem(
                category_id=product.category_id,
                brand_id=product.brand_id,
                unit_of_measure=product.unit_of_measure,
                image_url=product.image_url,
                name_zh=product.name_zh,
            )
            product.skus.append(sku)
            created.append(entry.sku_code)
        sku.sku_code = entry.sku_code
        sku.variant_attrs = entry.variant_attrs
        sku.sale_price = entry.sale_price
        sku.cost_price = entry.cost_price
        sku.other_cost = entry.other_cost
        sku.barcode = entry.barcode
        sku.reorder_level = entry.reorder_level
        sku.is_active = entry.is_active
        _set_sku_names(product, sku)
    return created, updated


@router.post("/products", response_model=InventoryProductOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_product(body: InventoryProductCreate, _admin: AdminOnly, db: DB) -> InventoryProduct:
    await _assert_category_exists(db, body.category_id)
    await _assert_brand_exists(db, body.brand_id)
    exists = await db.execute(select(InventoryProduct.id).where(InventoryProduct.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Product code already exists")
    if body.skus and any(entry.id is not None for entry in body.skus):
        raise HTTPException(status_code=422, detail="SKU id is not allowed when creating a product")

    product = InventoryProduct(**body.model_dump(exclude={"skus"}), skus=[])
    created: list[str] = []
    try:
        db.add(product)
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Product code already exists")
        if body.skus:
            created, _updated = await _apply_sku_inputs(db, product, body.skus)
            _validate_product_skus(product)
            _deactivate_skus_of_inactive_product(product)
            try:
                async with db.begin_nested():
                    await db.flush()
            except IntegrityError:
                raise HTTPException(status_code=409, detail="SKU code already exists")
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    product_id = product.id
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="inventory_products",
        record_id=product_id,
        new_values={**body.model_dump(mode="json", exclude={"skus"}), "created_skus": created},
        description=f"Created inventory product {body.code} {body.name_zh} with {len(created)} SKUs",
    )
    return await _get_product_or_404(db, product_id)


@router.get("/products/{product_id}", response_model=InventoryProductOut)
async def get_inventory_product(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> InventoryProduct:
    return await _get_product_or_404(db, product_id)


@router.patch("/products/{product_id}", response_model=InventoryProductOut)
async def update_inventory_product(
    product_id: uuid.UUID, body: InventoryProductUpdate, _admin: AdminOnly, db: DB
) -> InventoryProduct:
    product = await _get_product_or_404(db, product_id)
    update_data = body.model_dump(exclude_unset=True, exclude={"skus"})
    for required in ("code", "name_zh", "is_active"):
        if required in update_data and update_data[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} must not be null")

    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(
            select(InventoryProduct.id).where(InventoryProduct.code == new_code, InventoryProduct.id != product_id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Product code already exists")
    if "category_id" in update_data:
        await _assert_category_exists(db, update_data["category_id"])
    if "brand_id" in update_data:
        await _assert_brand_exists(db, update_data["brand_id"])
    if "options" in update_data and body.skus is None:
        _assert_options_cover_skus(update_data["options"], list(product.skus))

    old_values = {field: getattr(product, field) for field in update_data}
    created: list[str] = []
    updated: list[str] = []
    deactivated: list[str] = []
    try:
        for field, value in update_data.items():
            setattr(product, field, value)
        for field in ("category_id", "brand_id", "unit_of_measure"):
            if field in update_data:
                for sku in product.skus:
                    setattr(sku, field, getattr(product, field))
        if "name_zh" in update_data or "name_en" in update_data:
            for sku in product.skus:
                _set_sku_names(product, sku)
        if body.skus is not None:
            created, updated = await _apply_sku_inputs(db, product, body.skus)
            _validate_product_skus(product)
        deactivated = _deactivate_skus_of_inactive_product(product)
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Product or SKU code already exists")
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="inventory_products",
        record_id=product_id,
        old_values=old_values,
        new_values={
            **update_data,
            "created_skus": created,
            "updated_skus": updated,
            "deactivated_skus": deactivated,
        },
        description=(
            f"Updated inventory product {product.code}"
            f" ({len(created)} SKUs created, {len(updated)} updated)"
        ),
    )
    return await _get_product_or_404(db, product_id)


@router.post("/products/{product_id}/generate-skus", response_model=InventoryProductOut)
async def generate_inventory_product_skus(
    product_id: uuid.UUID, body: InventoryGenerateSkusRequest, _admin: AdminOnly, db: DB
) -> InventoryProduct:
    product = await _get_product_or_404(db, product_id)
    options = product.options or {}
    if not options:
        raise HTTPException(status_code=422, detail="Product has no options to generate SKUs from")

    keys = list(options.keys())
    option_key_set = set(keys)
    mismatched = [
        sku for sku in product.skus if sku.variant_attrs and set(sku.variant_attrs) != option_key_set
    ]
    if mismatched:
        missing_keys = [key for key in keys if any(key not in sku.variant_attrs for sku in mismatched)]
        raise HTTPException(
            status_code=409,
            detail=(
                f"SKUs {', '.join(sku.sku_code for sku in mismatched)} are missing option(s) "
                f"{', '.join(missing_keys)}; set them in the item editor before generating"
            ),
        )
    existing_attrs = [sku.variant_attrs for sku in product.skus if sku.variant_attrs]
    planned: list[tuple[str, dict[str, str]]] = []
    for combo in itertools.product(*(options[key] for key in keys)):
        attrs = dict(zip(keys, combo))
        if attrs in existing_attrs:
            continue
        planned.append((f"{product.code}-{'-'.join(combo)}", attrs))

    too_long = [code for code, _attrs in planned if len(code) > 100]
    if too_long:
        raise HTTPException(status_code=422, detail=f"Generated SKU code exceeds 100 characters: {', '.join(too_long)}")

    if planned:
        taken = await db.execute(
            select(InventoryItem.sku_code).where(InventoryItem.sku_code.in_([code for code, _a in planned]))
        )
        conflicts = sorted(taken.scalars().all())
        if conflicts:
            raise HTTPException(status_code=409, detail=f"SKU code already exists: {', '.join(conflicts)}")

        for code, attrs in planned:
            values = list(attrs.values())
            db.add(
                InventoryItem(
                    sku_code=code,
                    name_zh=f"{product.name_zh} {' / '.join(values)}",
                    name_en=f"{product.name_en} {' / '.join(values)}" if product.name_en else None,
                    category_id=product.category_id,
                    brand_id=product.brand_id,
                    unit_of_measure=product.unit_of_measure,
                    image_url=product.image_url,
                    product_id=product.id,
                    variant_attrs=attrs,
                    sale_price=body.sale_price,
                    cost_price=body.cost_price,
                    reorder_level=body.reorder_level,
                )
            )
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=409, detail="SKU code already exists")
        await db.commit()
        await audit_log_svc.log_audit(
            db,
            user_id=_admin.id,
            action="CREATE",
            table_name="inventory_products",
            record_id=product_id,
            new_values={"created_skus": [code for code, _a in planned]},
            description=f"Generated {len(planned)} SKUs for product {product.code}",
        )
    return await _get_product_or_404(db, product_id)


# ---- Items ----


@router.get("/items", response_model=list[InventoryItemOut])
async def list_inventory_items(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    category_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    low_stock: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[InventoryItem]:
    clauses = []
    if category_id is not None:
        clauses.append(InventoryItem.category_id.in_(_category_ids_with_children(category_id)))
    if brand_id is not None:
        clauses.append(InventoryItem.brand_id == brand_id)
    if product_id is not None:
        clauses.append(InventoryItem.product_id == product_id)
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
    items = list(result.scalars().all())
    await _attach_on_hand(db, items)
    return items


@router.post("/items", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(body: InventoryItemCreate, _admin: AdminOnly, db: DB) -> InventoryItem:
    await _assert_category_exists(db, body.category_id)
    await _assert_brand_exists(db, body.brand_id)
    await _validate_item_variant(db, body.product_id, body.variant_attrs)
    await _assert_product_active_for_item(db, body.product_id, body.is_active)

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
    await _attach_on_hand(db, [item])
    return item


@router.get("/items/{item_id}", response_model=InventoryItemOut)
async def get_inventory_item(item_id: uuid.UUID, _admin: AdminOnly, db: DB) -> InventoryItem:
    item = await _get_item_or_404(db, item_id)
    await _attach_on_hand(db, [item])
    return item


@router.patch("/items/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    item_id: uuid.UUID, body: InventoryItemUpdate, _admin: AdminOnly, db: DB
) -> InventoryItem:
    item = await _get_item_or_404(db, item_id)

    update_data = body.model_dump(exclude_unset=True)
    if "category_id" in update_data:
        await _assert_category_exists(db, update_data["category_id"])
    if "brand_id" in update_data:
        await _assert_brand_exists(db, update_data["brand_id"])

    if "product_id" in update_data and update_data["product_id"] is None:
        update_data["variant_attrs"] = None
    if "product_id" in update_data or "variant_attrs" in update_data:
        await _validate_item_variant(
            db,
            update_data.get("product_id", item.product_id),
            update_data.get("variant_attrs", item.variant_attrs),
            exclude_item_id=item_id,
        )

    if update_data.get("is_active") is True:
        await _assert_product_active_for_item(db, update_data.get("product_id", item.product_id), True)

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
    await _attach_on_hand(db, [item])
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
    created_at_clauses = []
    if date_from is not None:
        created_at_clauses.append(
            InventoryMovement.created_at >= datetime.combine(date_from, time.min, tzinfo=ATTENDANCE_TZ)
        )
    if date_to is not None:
        created_at_clauses.append(
            InventoryMovement.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=ATTENDANCE_TZ)
        )
    clauses += inventory_svc.movement_date_clause(created_at_clauses, date_from, date_to)

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
    brands = (await db.execute(select(InventoryBrand))).scalars().all()
    by_id = {c.id: c for c in categories}
    brand_name = {b.id: b.name_zh for b in brands}

    def category_path(category_id: uuid.UUID | None) -> str:
        category = by_id.get(category_id)
        if category is None:
            return ""
        parent = by_id.get(category.parent_id) if category.parent_id else None
        return f"{parent.name_zh} > {category.name_zh}" if parent else category.name_zh

    rows = [
        [
            item.sku_code,
            item.name_zh,
            item.name_en or "",
            category_path(item.category_id),
            item.unit_of_measure or "",
            item.barcode or "",
            item.cost_price if item.cost_price is not None else "",
            item.other_cost if item.other_cost is not None else "",
            item.sale_price if item.sale_price is not None else "",
            item.reorder_level,
            item.is_active,
            brand_name.get(item.brand_id, ""),
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
            "brand",
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


def _category_label_parts(label: str) -> list[str]:
    return [part.strip() for part in label.split(">")]


@router.post("/import/items", response_model=InventoryImportResult)
async def import_inventory_items(
    file: UploadFile, _admin: AdminOnly, db: DB
) -> InventoryImportResult:
    rows = await _read_csv_rows(file)

    categories = list((await db.execute(select(InventoryCategory))).scalars().all())
    top_level = [c for c in categories if c.parent_id is None]
    brands = list((await db.execute(select(InventoryBrand))).scalars().all())
    brand_by_name: dict[str, InventoryBrand] = {}
    for brand in brands:
        brand_by_name[brand.name_zh.strip().lower()] = brand
    for brand in brands:
        if brand.name_en:
            brand_by_name.setdefault(brand.name_en.strip().lower(), brand)
    existing_items = (
        await db.execute(select(InventoryItem))
    ).scalars().all()
    item_by_sku = {i.sku_code: i for i in existing_items}

    def names_of(category: InventoryCategory) -> set[str]:
        return {n for n in (category.name_zh.strip(), (category.name_en or "").strip()) if n}

    def resolve_category(label: str) -> InventoryCategory | tuple[str, ...]:
        parts = _category_label_parts(label)
        if len(parts) > 2 or not all(parts):
            raise ValueError(f"invalid category path: {label} (use 'Parent > Child', at most 2 levels)")
        if len(parts) == 1:
            matches = [c for c in categories if parts[0] in names_of(c)]
            if len(matches) > 1:
                raise ValueError(
                    f"category '{label}' is ambiguous ({len(matches)} matches); use the 'Parent > Child' path"
                )
            return matches[0] if matches else (parts[0],)
        parent = next((c for c in top_level if parts[0] in names_of(c)), None)
        if parent is None:
            return (parts[0], parts[1])
        child = next((c for c in categories if c.parent_id == parent.id and parts[1] in names_of(c)), None)
        return child if child is not None else (parts[0], parts[1])

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
            category_label = (row.get("category") or "").strip()
            category_ref = resolve_category(category_label) if category_label else None
            brand_id = None
            if "brand" in row and (row.get("brand") or "").strip():
                brand = brand_by_name.get((row.get("brand") or "").strip().lower())
                if brand is None:
                    raise ValueError(f"unknown brand: {(row.get('brand') or '').strip()}")
                brand_id = brand.id
            parsed.append(
                {
                    "row": idx,
                    "sku_code": sku,
                    "name_zh": name_zh,
                    "name_en": (row.get("name_en") or "").strip() or None,
                    "category_ref": category_ref,
                    "unit_of_measure": (row.get("unit_of_measure") or "").strip() or None,
                    "has_barcode": "barcode" in row,
                    "has_other_cost": "other_cost" in row,
                    "has_brand": "brand" in row,
                    "brand_id": brand_id,
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

    created_categories: dict[tuple[str, ...], InventoryCategory] = {}

    def new_category(path: tuple[str, ...]) -> InventoryCategory:
        if path in created_categories:
            return created_categories[path]
        parent_id = None
        if len(path) == 2:
            parent = next((c for c in top_level if path[0] in names_of(c)), None) or new_category((path[0],))
            parent_id = parent.id
        category = InventoryCategory(id=uuid.uuid4(), name_zh=path[-1], parent_id=parent_id)
        db.add(category)
        created_categories[path] = category
        return category

    created = updated = 0
    for row in parsed:
        category_id = None
        ref = row["category_ref"]
        if ref is not None:
            category_id = (new_category(ref) if isinstance(ref, tuple) else ref).id

        item = item_by_sku.get(row["sku_code"])
        if item is None:
            item = InventoryItem(
                sku_code=row["sku_code"],
                name_zh=row["name_zh"],
                name_en=row["name_en"],
                category_id=category_id,
                brand_id=row["brand_id"],
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
            if row["has_brand"]:
                item.brand_id = row["brand_id"]
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
