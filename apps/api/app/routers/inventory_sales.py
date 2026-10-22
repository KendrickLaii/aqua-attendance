import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminOnly, DB
from app.models.inventory import InventoryItem, InventoryStock
from app.models.inventory_invoicing import InventoryInvoice
from app.models.inventory_sales import (
    Customer,
    DeliveryOrder,
    DeliveryOrderLine,
    SalesOrder,
    SalesOrderLine,
)
from app.models.location import Location
from app.models.unit import Unit
from app.schemas.inventory_sales import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    DeliveryOrderCreate,
    DeliveryOrderLineIn,
    DeliveryOrderOut,
    DeliveryOrderUpdate,
    ProformaDoc,
    ProformaRequest,
    SalesOrderCreate,
    SalesOrderOut,
    SalesOrderUpdate,
)
from app.services import audit_log as audit_log_svc
from app.services import doc_numbers as doc_numbers_svc
from app.services import inventory as inventory_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/inventory", tags=["inventory"])

# Confirmed SOs reserve stock; a reserve shortfall blocks confirmation.
ALLOW_RESERVE_SHORTFALL = False


async def _assert_location_exists(db: DB, location_id: uuid.UUID) -> None:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")
    if not location.is_active:
        raise HTTPException(status_code=422, detail=f"location {location.name_en or location_id} is inactive")


async def _get_customer_or_422(db: DB, customer_id: uuid.UUID) -> Customer:
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=422, detail="customer_id does not reference an existing customer")
    if not customer.is_active:
        raise HTTPException(status_code=422, detail=f"customer {customer.code} is inactive")
    return customer


async def _get_item_or_422(db: DB, item_id: uuid.UUID) -> InventoryItem:
    item = await db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=422, detail=f"unknown item_id: {item_id}")
    if not item.is_active:
        raise HTTPException(status_code=422, detail=f"item {item.sku_code} is inactive")
    return item


async def _get_so_or_404(db: DB, so_id: uuid.UUID) -> SalesOrder:
    so = await db.get(SalesOrder, so_id)
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return so


async def _get_do_or_404(db: DB, do_id: uuid.UUID) -> DeliveryOrder:
    do = await db.get(DeliveryOrder, do_id)
    if not do:
        raise HTTPException(status_code=404, detail="Delivery order not found")
    return do


async def _lock_or_404(db: DB, model, row_id: uuid.UUID, label: str):
    """SELECT ... FOR UPDATE on a document row; 404 when missing.

    Confirm/void/cancel handlers take this lock before re-checking status so
    the status transition and its side effects are serialized per document.
    """
    result = await db.execute(select(model).where(model.id == row_id).with_for_update())
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


async def _so_lines(db: DB, so_id: uuid.UUID) -> list[SalesOrderLine]:
    return list(
        (
            await db.execute(
                select(SalesOrderLine)
                .where(SalesOrderLine.so_id == so_id)
                .order_by(SalesOrderLine.id)
            )
        ).scalars().all()
    )


async def _do_lines(db: DB, do_id: uuid.UUID) -> list[DeliveryOrderLine]:
    return list(
        (
            await db.execute(
                select(DeliveryOrderLine)
                .where(DeliveryOrderLine.do_id == do_id)
                .order_by(DeliveryOrderLine.id)
            )
        ).scalars().all()
    )


async def _items_map(db: DB, lines) -> dict[uuid.UUID, InventoryItem]:
    ids = {line.item_id for line in lines}
    if not ids:
        return {}
    result = await db.execute(select(InventoryItem).where(InventoryItem.id.in_(ids)))
    return {item.id: item for item in result.scalars().all()}


async def _so_detail(db: DB, so: SalesOrder) -> dict:
    lines = await _so_lines(db, so.id)
    customer = await db.get(Customer, so.customer_id)
    location = await db.get(Location, so.location_id)
    out = {
        f: getattr(so, f)
        for f in SalesOrderOut.model_fields
        if f not in ("lines", "customer_name", "customer_code", "location_name")
    }
    out["lines"] = lines
    out["customer_name"] = customer.name_zh if customer else None
    out["customer_code"] = customer.code if customer else None
    out["location_name"] = location.name_en if location else None
    return out


async def _do_detail(db: DB, do: DeliveryOrder) -> dict:
    lines = await _do_lines(db, do.id)
    items = await _items_map(db, lines)
    so = await db.get(SalesOrder, do.so_id)
    customer = await db.get(Customer, do.customer_id)
    location = await db.get(Location, do.location_id)
    out = {
        f: getattr(do, f)
        for f in DeliveryOrderOut.model_fields
        if f not in ("lines", "so_no_ref", "customer_name", "location_name")
    }
    out["lines"] = [
        {
            "id": line.id,
            "so_line_id": line.so_line_id,
            "item_id": line.item_id,
            "qty": line.qty,
            "sku_code": items[line.item_id].sku_code if line.item_id in items else None,
            "name_zh": items[line.item_id].name_zh if line.item_id in items else None,
        }
        for line in lines
    ]
    out["so_no_ref"] = so.so_no if so else None
    out["customer_name"] = customer.name_zh if customer else None
    out["location_name"] = location.name_en if location else None
    return out


def _so_line_amount(qty: int, unit_price: float, discount_amount: float) -> Decimal:
    return max(Decimal("0"), Decimal(str(qty)) * Decimal(str(unit_price)) - Decimal(str(discount_amount)))


def _so_total(lines: list[SalesOrderLine], header_discount: float) -> Decimal:
    subtotal = sum((Decimal(str(line.amount)) for line in lines), Decimal("0"))
    return max(Decimal("0"), subtotal - Decimal(str(header_discount)))


async def _build_so_lines(db: DB, so: SalesOrder, line_inputs) -> list[SalesOrderLine]:
    lines = []
    for line_in in line_inputs:
        item = await _get_item_or_422(db, line_in.item_id)
        amount = _so_line_amount(line_in.qty, line_in.unit_price, line_in.discount_amount)
        line = SalesOrderLine(
            so=so,
            item_id=item.id,
            sku_code=item.sku_code,
            name_zh=item.name_zh,
            qty=line_in.qty,
            shipped_qty=0,
            unit_price=line_in.unit_price,
            discount_amount=line_in.discount_amount,
            amount=amount,
        )
        db.add(line)
        lines.append(line)
    return lines


async def _recompute_so_status(db: DB, so: SalesOrder) -> None:
    if so.status in ("draft", "cancelled"):
        return
    lines = await _so_lines(db, so.id)
    if lines and all(line.shipped_qty >= line.qty for line in lines):
        so.status = "fulfilled"
    elif any(line.shipped_qty > 0 for line in lines):
        so.status = "partial"
    else:
        so.status = "confirmed"


# ---- Customers ----


@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    is_active: bool | None = None,
    type: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[Customer]:
    clauses = []
    if is_active is not None:
        clauses.append(Customer.is_active == is_active)
    if type is not None:
        clauses.append(Customer.type == type)
    if search:
        clauses.append(
            or_(
                ilike_contains(Customer.code, search),
                ilike_contains(Customer.name_zh, search),
                ilike_contains(Customer.name_en, search),
                ilike_contains(Customer.contact_name, search),
            )
        )

    count_q = select(func.count()).select_from(Customer)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(Customer)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(body: CustomerCreate, _admin: AdminOnly, db: DB) -> Customer:
    exists = await db.execute(select(Customer).where(Customer.code == body.code))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Customer code already exists")
    if body.student_unit_id:
        unit = await db.get(Unit, body.student_unit_id)
        if not unit or unit.unit_type != "student":
            raise HTTPException(status_code=422, detail="student_unit_id does not reference a student")
    customer = Customer(**body.model_dump())
    db.add(customer)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Customer code already exists")
    await db.commit()
    await db.refresh(customer)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="customers",
        record_id=customer.id,
        new_values=body.model_dump(),
        description=f"Created customer {customer.code} {customer.name_zh}",
    )
    return customer


@router.post("/customers/from-student/{unit_id}", response_model=CustomerOut)
async def create_customer_from_student(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> Customer:
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if unit.unit_type != "student":
        raise HTTPException(status_code=422, detail="unit is not a student")

    existing = await db.execute(
        select(Customer).where(Customer.student_unit_id == unit_id)
    )
    customer = existing.scalar_one_or_none()
    if customer:
        return customer

    code = f"C-{unit.code}"
    clash = await db.execute(select(Customer).where(Customer.code == code))
    n = 2
    while clash.scalar_one_or_none():
        code = f"C-{unit.code}-{n}"
        n += 1
        clash = await db.execute(select(Customer).where(Customer.code == code))

    customer = Customer(
        code=code,
        name_zh=unit.full_name,
        name_en=unit.english_name,
        type="individual",
        contact_name=unit.emergency_contact_name,
        phone=unit.phone or unit.emergency_contact_phone,
        email=unit.email,
        address=unit.address,
        student_unit_id=unit.id,
        is_active=True,
    )
    db.add(customer)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Lost a race on the unique student_unit_id/code — return the winner.
        existing = await db.execute(
            select(Customer).where(Customer.student_unit_id == unit_id)
        )
        customer = existing.scalar_one_or_none()
        if customer:
            return customer
        raise HTTPException(status_code=409, detail="customer code already exists")
    await db.commit()
    await db.refresh(customer)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="customers",
        record_id=customer.id,
        new_values={"code": code, "name_zh": unit.full_name, "student_unit_id": str(unit.id)},
        description=f"Created customer {code} from student {unit.code}",
    )
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: uuid.UUID, _admin: AdminOnly, db: DB) -> Customer:
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(customer_id: uuid.UUID, body: CustomerUpdate, _admin: AdminOnly, db: DB) -> Customer:
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = body.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(
            select(Customer).where(Customer.code == new_code, Customer.id != customer_id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Customer code already exists")

    old_values = {field: getattr(customer, field) for field in update_data}
    for field, value in update_data.items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="customers",
        record_id=customer_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated customer {customer.code} {customer.name_zh}",
    )
    return customer


# ---- Sales orders ----


@router.get("/sales-orders", response_model=list[SalesOrderOut])
async def list_sales_orders(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    clauses = []
    if customer_id is not None:
        clauses.append(SalesOrder.customer_id == customer_id)
    if location_id is not None:
        clauses.append(SalesOrder.location_id == location_id)
    if status is not None:
        clauses.append(SalesOrder.status == status)
    if date_from is not None:
        clauses.append(SalesOrder.order_date >= date_from)
    if date_to is not None:
        clauses.append(SalesOrder.order_date <= date_to)

    count_q = select(func.count()).select_from(SalesOrder)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(SalesOrder)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(SalesOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [await _so_detail(db, so) for so in result.scalars().all()]


@router.post("/sales-orders", response_model=SalesOrderOut, status_code=status.HTTP_201_CREATED)
async def create_sales_order(body: SalesOrderCreate, _admin: AdminOnly, db: DB) -> dict:
    customer = await _get_customer_or_422(db, body.customer_id)
    await _assert_location_exists(db, body.location_id)

    so_no = await doc_numbers_svc.allocate_doc_no(db, location_id=body.location_id, doc_type="SO")
    so = SalesOrder(
        so_no=so_no,
        customer_id=body.customer_id,
        buyer_name=customer.name_zh,
        location_id=body.location_id,
        order_date=body.order_date,
        discount_amount=body.discount_amount,
        notes=body.notes,
        created_by=_admin.id,
    )
    db.add(so)
    lines = await _build_so_lines(db, so, body.lines)
    so.total = _so_total(lines, so.discount_amount)
    await db.flush()
    so_id = so.id
    await db.commit()

    result = await db.execute(select(SalesOrder).where(SalesOrder.id == so_id))
    so = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="sales_orders",
        record_id=so_id,
        new_values={**body.model_dump(), "so_no": so_no, "total": so.total},
        description=f"Created sales order {so_no}",
    )
    return await _so_detail(db, so)


@router.get("/sales-orders/{so_id}", response_model=SalesOrderOut)
async def get_sales_order(so_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    so = await _get_so_or_404(db, so_id)
    return await _so_detail(db, so)


@router.patch("/sales-orders/{so_id}", response_model=SalesOrderOut)
async def update_sales_order(
    so_id: uuid.UUID, body: SalesOrderUpdate, _admin: AdminOnly, db: DB
) -> dict:
    so = await _get_so_or_404(db, so_id)
    if so.status != "draft":
        raise HTTPException(status_code=409, detail=f"sales order is {so.status}; only drafts can be edited")

    update_data = body.model_dump(exclude_unset=True)
    old_values: dict = {}
    if "customer_id" in update_data:
        customer = await _get_customer_or_422(db, update_data["customer_id"])
        update_data["buyer_name"] = customer.name_zh
    if "location_id" in update_data:
        await _assert_location_exists(db, update_data["location_id"])
    for field in ("customer_id", "location_id", "order_date", "discount_amount", "notes"):
        if field in update_data:
            old_values[field] = getattr(so, field)
            setattr(so, field, update_data[field])
    if "buyer_name" in update_data:
        old_values["buyer_name"] = None
        so.buyer_name = update_data["buyer_name"]

    if "lines" in update_data and body.lines is not None:
        existing = await _so_lines(db, so_id)
        old_values["lines"] = [{"item_id": l.item_id, "qty": l.qty} for l in existing]
        for line in existing:
            await db.delete(line)
        await db.flush()
        lines = await _build_so_lines(db, so, body.lines)
        so.total = _so_total(lines, so.discount_amount)
    else:
        await db.flush()
        so.total = _so_total(await _so_lines(db, so_id), so.discount_amount)

    await db.commit()
    result = await db.execute(select(SalesOrder).where(SalesOrder.id == so_id))
    so = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="sales_orders",
        record_id=so_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated sales order {so.so_no}",
    )
    return await _so_detail(db, so)


@router.delete("/sales-orders/{so_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sales_order(so_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    so = await _get_so_or_404(db, so_id)
    if so.status != "draft":
        raise HTTPException(status_code=409, detail=f"sales order is {so.status}; only drafts can be deleted")
    so_no = so.so_no
    await db.delete(so)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="sales_orders",
        record_id=so_id,
        description=f"Deleted draft sales order {so_no}",
    )


async def confirm_so_tx(db: DB, so: SalesOrder) -> None:
    """Reserve every line and mark the SO confirmed. Caller commits."""
    lines = await _so_lines(db, so.id)
    if not lines:
        raise HTTPException(status_code=422, detail="sales order has no lines")
    for line in lines:
        if ALLOW_RESERVE_SHORTFALL:
            stock = (
                await db.execute(
                    select(InventoryStock).where(
                        InventoryStock.item_id == line.item_id,
                        InventoryStock.location_id == so.location_id,
                    )
                )
            ).scalar_one_or_none()
            if stock and stock.quantity - stock.reserved >= line.qty:
                await inventory_svc.reserve(
                    db, item_id=line.item_id, location_id=so.location_id, quantity=line.qty
                )
        else:
            await inventory_svc.reserve(
                db, item_id=line.item_id, location_id=so.location_id, quantity=line.qty
            )
    so.status = "confirmed"
    await db.flush()


@router.post("/sales-orders/{so_id}/confirm", response_model=SalesOrderOut)
async def confirm_sales_order(so_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    so = await _lock_or_404(db, SalesOrder, so_id, "Sales order")
    if so.status in ("confirmed", "partial", "fulfilled"):
        return await _so_detail(db, so)
    if so.status != "draft":
        raise HTTPException(status_code=409, detail=f"sales order is {so.status}; cannot confirm")

    await confirm_so_tx(db, so)
    await db.commit()
    result = await db.execute(select(SalesOrder).where(SalesOrder.id == so_id))
    so = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="sales_orders",
        record_id=so_id,
        old_values={"status": "draft"},
        new_values={"status": "confirmed"},
        description=f"Confirmed sales order {so.so_no}",
    )
    return await _so_detail(db, so)


@router.post("/sales-orders/{so_id}/cancel", response_model=SalesOrderOut)
async def cancel_sales_order(so_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    so = await _lock_or_404(db, SalesOrder, so_id, "Sales order")
    if so.status == "cancelled":
        return await _so_detail(db, so)
    if so.status == "fulfilled":
        raise HTTPException(status_code=409, detail="fulfilled sales order cannot be cancelled")

    lines = await _so_lines(db, so_id)
    if so.status in ("confirmed", "partial"):
        for line in lines:
            remaining = line.qty - line.shipped_qty
            if remaining > 0:
                await inventory_svc.release(
                    db, item_id=line.item_id, location_id=so.location_id, quantity=remaining
                )

    old_status = so.status
    so.status = "cancelled"
    await db.commit()
    result = await db.execute(select(SalesOrder).where(SalesOrder.id == so_id))
    so = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="sales_orders",
        record_id=so_id,
        old_values={"status": old_status},
        new_values={"status": "cancelled"},
        description=f"Cancelled sales order {so.so_no}",
    )
    return await _so_detail(db, so)


@router.post("/sales-orders/{so_id}/proforma", response_model=SalesOrderOut)
async def issue_proforma(
    so_id: uuid.UUID, body: ProformaRequest, _admin: AdminOnly, db: DB
) -> dict:
    so = await _get_so_or_404(db, so_id)
    if so.pf_no:
        if body.pf_valid_until:
            so.pf_valid_until = body.pf_valid_until
            await db.commit()
            await audit_log_svc.log_audit(
                db,
                user_id=_admin.id,
                action="UPDATE",
                table_name="sales_orders",
                record_id=so_id,
                new_values={"pf_valid_until": so.pf_valid_until},
                description=f"Updated proforma validity for {so.so_no}",
            )
        return await _so_detail(db, so)
    if so.status not in ("draft", "confirmed"):
        raise HTTPException(status_code=409, detail=f"sales order is {so.status}; cannot issue proforma")

    so.pf_no = await doc_numbers_svc.allocate_doc_no(db, location_id=so.location_id, doc_type="PF")
    so.pf_issued_at = datetime.now(timezone.utc)
    so.pf_valid_until = body.pf_valid_until
    await db.commit()
    result = await db.execute(select(SalesOrder).where(SalesOrder.id == so_id))
    so = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="sales_orders",
        record_id=so_id,
        new_values={"pf_no": so.pf_no, "pf_issued_at": so.pf_issued_at, "pf_valid_until": so.pf_valid_until},
        description=f"Issued proforma {so.pf_no} for sales order {so.so_no}",
    )
    return await _so_detail(db, so)


@router.get("/sales-orders/{so_id}/proforma", response_model=ProformaDoc)
async def get_proforma(so_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    so = await _get_so_or_404(db, so_id)
    if not so.pf_no:
        raise HTTPException(status_code=409, detail="no proforma issued for this sales order")

    lines = await _so_lines(db, so_id)
    customer = await db.get(Customer, so.customer_id)
    location = await db.get(Location, so.location_id)
    return {
        "pf_no": so.pf_no,
        "so_no": so.so_no,
        "issued_at": so.pf_issued_at,
        "valid_until": so.pf_valid_until,
        "order_date": so.order_date,
        "location_name_zh": location.name_zh if location else None,
        "location_name_en": location.name_en if location else None,
        "location_address": location.address if location else None,
        "location_phone": location.phone if location else None,
        "location_email": location.email if location else None,
        "customer_name": so.buyer_name,
        "customer_code": customer.code if customer else None,
        "customer_contact": customer.contact_name if customer else None,
        "customer_phone": customer.phone if customer else None,
        "customer_email": customer.email if customer else None,
        "customer_address": customer.address if customer else None,
        "lines": lines,
        "discount_amount": so.discount_amount,
        "subtotal": float(sum((Decimal(str(l.amount)) for l in lines), Decimal("0"))),
        "total": so.total,
        "notes": so.notes,
    }


# ---- Delivery orders ----


@router.get("/delivery-orders", response_model=list[DeliveryOrderOut])
async def list_delivery_orders(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    customer_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    so_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[dict]:
    clauses = []
    if customer_id is not None:
        clauses.append(DeliveryOrder.customer_id == customer_id)
    if location_id is not None:
        clauses.append(DeliveryOrder.location_id == location_id)
    if so_id is not None:
        clauses.append(DeliveryOrder.so_id == so_id)
    if status is not None:
        clauses.append(DeliveryOrder.status == status)
    if search:
        clauses.append(
            or_(
                ilike_contains(DeliveryOrder.do_no, search),
                ilike_contains(Customer.code, search),
                ilike_contains(Customer.name_zh, search),
                ilike_contains(Customer.name_en, search),
            )
        )

    count_q = select(func.count()).select_from(DeliveryOrder)
    q = select(DeliveryOrder)
    if search:
        count_q = count_q.join(Customer, DeliveryOrder.customer_id == Customer.id)
        q = q.join(Customer, DeliveryOrder.customer_id == Customer.id)
    if clauses:
        count_q = count_q.where(*clauses)
        q = q.where(*clauses)
    total = await db.scalar(count_q) or 0
    q = q.order_by(DeliveryOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [await _do_detail(db, do) for do in result.scalars().all()]


async def _validate_do_lines_against_so(
    db: DB, so: SalesOrder, line_inputs
) -> dict[uuid.UUID, SalesOrderLine]:
    so_lines = await _so_lines(db, so.id)
    by_id = {line.id: line for line in so_lines}
    resolved: dict[uuid.UUID, SalesOrderLine] = {}
    for line_in in line_inputs:
        so_line = by_id.get(line_in.so_line_id)
        if so_line is None:
            raise HTTPException(status_code=422, detail=f"so_line_id {line_in.so_line_id} not on this SO")
        if so_line.item_id != line_in.item_id:
            raise HTTPException(status_code=422, detail="item_id does not match the SO line")
        resolved[so_line.id] = so_line
    return resolved


async def create_do_tx(
    db: DB,
    so: SalesOrder,
    *,
    delivery_date: date,
    notes: str | None,
    line_inputs: list[DeliveryOrderLineIn],
    user,
) -> DeliveryOrder:
    """Validate + create a draft DO (prefills remaining qty when no lines). Caller commits.

    The SO row is locked here so the status check and DO creation serialize
    against a concurrent cancel/confirm of the same SO.
    """
    so = await _lock_or_404(db, SalesOrder, so.id, "Sales order")
    if so.status not in ("confirmed", "partial"):
        raise HTTPException(status_code=422, detail=f"SO {so.so_no} is {so.status}; cannot deliver")

    if not line_inputs:
        remaining = [l for l in await _so_lines(db, so.id) if l.qty - l.shipped_qty > 0]
        line_inputs = [
            DeliveryOrderLineIn(so_line_id=l.id, item_id=l.item_id, qty=l.qty - l.shipped_qty)
            for l in remaining
        ]
        if not line_inputs:
            raise HTTPException(status_code=422, detail="SO is fully shipped")

    for line in line_inputs:
        await _get_item_or_422(db, line.item_id)
    await _validate_do_lines_against_so(db, so, line_inputs)

    do_no = await doc_numbers_svc.allocate_doc_no(db, location_id=so.location_id, doc_type="DO")
    do = DeliveryOrder(
        do_no=do_no,
        so_id=so.id,
        customer_id=so.customer_id,
        location_id=so.location_id,
        delivery_date=delivery_date,
        notes=notes,
        created_by=user.id,
    )
    db.add(do)
    for line in line_inputs:
        db.add(
            DeliveryOrderLine(
                do=do, so_line_id=line.so_line_id, item_id=line.item_id, qty=line.qty
            )
        )
    await db.flush()
    return do


@router.post("/delivery-orders", response_model=DeliveryOrderOut, status_code=status.HTTP_201_CREATED)
async def create_delivery_order(body: DeliveryOrderCreate, _admin: AdminOnly, db: DB) -> dict:
    so = await _get_so_or_404(db, body.so_id)
    do = await create_do_tx(
        db,
        so,
        delivery_date=body.delivery_date,
        notes=body.notes,
        line_inputs=list(body.lines),
        user=_admin,
    )
    do_no = do.do_no
    do_id = do.id
    await db.commit()

    result = await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))
    do = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="delivery_orders",
        record_id=do_id,
        new_values={**body.model_dump(), "do_no": do_no},
        description=f"Created delivery order {do_no} for {so.so_no}",
    )
    return await _do_detail(db, do)


@router.get("/delivery-orders/{do_id}", response_model=DeliveryOrderOut)
async def get_delivery_order(do_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    do = await _get_do_or_404(db, do_id)
    return await _do_detail(db, do)


@router.patch("/delivery-orders/{do_id}", response_model=DeliveryOrderOut)
async def update_delivery_order(
    do_id: uuid.UUID, body: DeliveryOrderUpdate, _admin: AdminOnly, db: DB
) -> dict:
    do = await _get_do_or_404(db, do_id)
    if do.status != "draft":
        raise HTTPException(status_code=409, detail=f"delivery order is {do.status}; only drafts can be edited")

    update_data = body.model_dump(exclude_unset=True)
    old_values: dict = {}
    for field in ("delivery_date", "notes"):
        if field in update_data:
            old_values[field] = getattr(do, field)
            setattr(do, field, update_data[field])

    if "lines" in update_data and body.lines is not None:
        if not body.lines:
            raise HTTPException(status_code=422, detail="a delivery order needs at least one line")
        for line_in in body.lines:
            await _get_item_or_422(db, line_in.item_id)
        so = await _get_so_or_404(db, do.so_id)
        await _validate_do_lines_against_so(db, so, body.lines)
        existing = await _do_lines(db, do_id)
        old_values["lines"] = [{"item_id": l.item_id, "qty": l.qty} for l in existing]
        for line in existing:
            await db.delete(line)
        await db.flush()
        for line_in in body.lines:
            db.add(
                DeliveryOrderLine(
                    do=do,
                    so_line_id=line_in.so_line_id,
                    item_id=line_in.item_id,
                    qty=line_in.qty,
                )
            )

    await db.commit()
    result = await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))
    do = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="delivery_orders",
        record_id=do_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated delivery order {do.do_no}",
    )
    return await _do_detail(db, do)


@router.delete("/delivery-orders/{do_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_delivery_order(do_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    do = await _get_do_or_404(db, do_id)
    if do.status != "draft":
        raise HTTPException(status_code=409, detail=f"delivery order is {do.status}; only drafts can be deleted")
    do_no = do.do_no
    await db.delete(do)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="delivery_orders",
        record_id=do_id,
        description=f"Deleted draft delivery order {do_no}",
    )


async def confirm_do_tx(db: DB, do: DeliveryOrder, user) -> None:
    """Validate + ship every DO line and mark the DO confirmed. Caller commits.

    Locks the parent SO row before checking per-line remaining quantities.
    """
    so = await _lock_or_404(db, SalesOrder, do.so_id, "Sales order")
    so_lines = {line.id: line for line in await _so_lines(db, so.id)}
    for line in await _do_lines(db, do.id):
        so_line = so_lines.get(line.so_line_id)
        if so_line is None:
            raise HTTPException(status_code=422, detail="delivery line references a removed SO line")
        if line.qty > so_line.qty - so_line.shipped_qty:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"over-shipment for {so_line.sku_code}: ordered {so_line.qty}, "
                    f"shipped {so_line.shipped_qty}, this DO {line.qty}"
                ),
            )

    for line in await _do_lines(db, do.id):
        so_line = so_lines[line.so_line_id]
        await _get_item_or_422(db, line.item_id)
        await inventory_svc.release(
            db, item_id=line.item_id, location_id=do.location_id, quantity=line.qty
        )
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=do.location_id,
            type="out",
            quantity=line.qty,
            reason=f"DO {do.do_no}",
            reason_code="sale",
            reference=f"DO:{do.id}:{line.id}",
            user=user,
        )
        so_line.shipped_qty += line.qty
    await _recompute_so_status(db, so)
    do.status = "confirmed"
    await db.flush()


@router.post("/delivery-orders/{do_id}/confirm", response_model=DeliveryOrderOut)
async def confirm_delivery_order(do_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    do = await _lock_or_404(db, DeliveryOrder, do_id, "Delivery order")
    if do.status == "confirmed":
        return await _do_detail(db, do)
    if do.status != "draft":
        raise HTTPException(status_code=409, detail=f"delivery order is {do.status}; cannot confirm")

    await confirm_do_tx(db, do, _admin)
    await db.commit()
    result = await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))
    do = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="delivery_orders",
        record_id=do_id,
        old_values={"status": "draft"},
        new_values={"status": "confirmed"},
        description=f"Confirmed delivery order {do.do_no}",
    )
    return await _do_detail(db, do)


@router.post("/delivery-orders/{do_id}/void", response_model=DeliveryOrderOut)
async def void_delivery_order(do_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    do = await _lock_or_404(db, DeliveryOrder, do_id, "Delivery order")
    if do.status == "void":
        return await _do_detail(db, do)
    if do.status != "confirmed":
        raise HTTPException(status_code=409, detail=f"delivery order is {do.status}; cannot void")

    invoiced = await db.execute(
        select(InventoryInvoice.id).where(
            InventoryInvoice.do_id == do_id, InventoryInvoice.status != "void"
        ).limit(1)
    )
    if invoiced.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="delivery order has a non-void invoice; void or delete the invoice first",
        )

    so = await _lock_or_404(db, SalesOrder, do.so_id, "Sales order")
    so_lines = {line.id: line for line in await _so_lines(db, so.id)}
    for line in await _do_lines(db, do_id):
        so_line = so_lines.get(line.so_line_id)
        await inventory_svc.apply_movement(
            db,
            item_id=line.item_id,
            location_id=do.location_id,
            type="in",
            quantity=line.qty,
            reason=f"void DO {do.do_no}",
            reason_code="other",
            reference=f"DO-VOID:{do.id}:{line.id}",
            user=_admin,
        )
        if so_line:
            so_line.shipped_qty = max(0, so_line.shipped_qty - line.qty)
        if so.status != "cancelled":
            await inventory_svc.reserve(
                db, item_id=line.item_id, location_id=do.location_id, quantity=line.qty
            )
    await _recompute_so_status(db, so)

    do.status = "void"
    await db.commit()
    result = await db.execute(select(DeliveryOrder).where(DeliveryOrder.id == do_id))
    do = result.scalar_one()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="delivery_orders",
        record_id=do_id,
        old_values={"status": "confirmed"},
        new_values={"status": "void"},
        description=f"Voided delivery order {do.do_no}",
    )
    return await _do_detail(db, do)
