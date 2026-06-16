import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly
from app.models.attendance import AttendanceEvent
from app.models.product import Product
from app.models.staff_profile import StaffProfile
from app.models.student_profile import StudentProfile
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services import product as product_svc
from app.utils.search import ilike_contains

router = APIRouter(prefix="/products", tags=["products"])

_VALID_ATTENDANCE_STATUSES = frozenset({"checked_in", "checked_out"})

_PRODUCT_LOAD_OPTIONS = (
    selectinload(Product.registered_location),
    selectinload(Product.scan_locations),
    selectinload(Product.student_profile),
    selectinload(Product.staff_profile),
)


def _product_filters(
    *,
    product_type: str | None,
    is_active: bool | None,
    search: str | None,
    attendance_status: str | None,
) -> list:
    clauses = []
    if product_type:
        clauses.append(Product.product_type == product_type)
    if is_active is not None:
        clauses.append(Product.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(Product.code, search),
                ilike_contains(Product.full_name, search),
                ilike_contains(Product.english_name, search),
            )
        )
    if attendance_status:
        clauses.append(Product.attendance_status == attendance_status)
    return clauses


@router.get("", response_model=list[ProductOut])
async def list_products(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    product_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    attendance_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[ProductOut]:
    if attendance_status and attendance_status not in _VALID_ATTENDANCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="attendance_status must be checked_in or checked_out",
        )

    clauses = _product_filters(
        product_type=product_type,
        is_active=is_active,
        search=search,
        attendance_status=attendance_status,
    )

    count_q = select(func.count()).select_from(Product)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(Product).options(*_PRODUCT_LOAD_OPTIONS)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(Product.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return [ProductOut.from_product(product) for product in result.scalars().all()]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductCreate, _admin: AdminOnly, db: DB) -> ProductOut:
    existing = await db.execute(select(Product).where(Product.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Product code already exists")

    _registered, scan_locs = await product_svc.resolve_product_locations(
        db,
        registered_location_id=body.registered_location_id,
        scan_location_ids=body.scan_location_ids,
    )

    product_data = body.model_dump(
        exclude={"scan_location_ids", "student_profile", "staff_profile"}
    )
    product = Product(**product_data)
    product.scan_locations = scan_locs
    db.add(product)
    await db.flush()

    # Create corresponding profile in the same transaction
    if product.product_type == "student" and body.student_profile:
        db.add(StudentProfile(id=product.id, **body.student_profile.model_dump()))
    elif product.product_type == "staff" and body.staff_profile:
        db.add(StaffProfile(id=product.id, **body.staff_profile.model_dump()))

    await db.commit()

    loaded = await product_svc.load_product_with_locations(db, product.id)
    assert loaded is not None
    return ProductOut.from_product(loaded)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> ProductOut:
    product = await product_svc.load_product_with_locations(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.from_product(product)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, body: ProductUpdate, _admin: AdminOnly, db: DB) -> ProductOut:
    result = await db.execute(
        select(Product)
        .options(*_PRODUCT_LOAD_OPTIONS)
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_unset=True)
    scan_ids = update_data.pop("scan_location_ids", None)
    registered_location_id = update_data.pop("registered_location_id", None)

    if "code" in update_data:
        dup = await db.execute(
            select(Product).where(Product.code == update_data["code"], Product.id != product_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Product code already exists")

    if registered_location_id is not None or scan_ids is not None:
        resolved_registered_id = (
            registered_location_id if registered_location_id is not None else product.registered_location_id
        )
        resolved_scan_ids = (
            scan_ids
            if scan_ids is not None
            else [loc.id for loc in product.scan_locations]
        )
        _registered, scan_locs = await product_svc.resolve_product_locations(
            db,
            registered_location_id=resolved_registered_id,
            scan_location_ids=resolved_scan_ids,
        )
        product.registered_location_id = resolved_registered_id
        await product_svc.replace_scan_locations(product, scan_locs)

    for field, value in update_data.items():
        setattr(product, field, value)
    await db.commit()

    loaded = await product_svc.load_product_with_locations(db, product_id)
    assert loaded is not None
    return ProductOut.from_product(loaded)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    has_events = await db.execute(
        select(AttendanceEvent.id).where(AttendanceEvent.product_id == product_id).limit(1)
    )
    if has_events.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Product has attendance records. Set it inactive instead of deleting.",
        )

    await db.delete(product)
    await db.commit()
