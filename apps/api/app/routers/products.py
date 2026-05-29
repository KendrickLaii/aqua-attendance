import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.deps import DB, AdminOnly
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

_VALID_ATTENDANCE_STATUSES = frozenset({"checked_in", "checked_out"})
_VALID_EMPLOYMENT_TYPES = frozenset({"part_time", "full_time"})


def _product_filters(
    *,
    product_type: str | None,
    is_active: bool | None,
    search: str | None,
    attendance_status: str | None,
    employment_type: str | None,
) -> list:
    clauses = []
    if product_type:
        clauses.append(Product.product_type == product_type)
    if is_active is not None:
        clauses.append(Product.is_active == is_active)
    if search:
        clauses.append(
            Product.code.ilike(f"%{search}%")
            | Product.full_name.ilike(f"%{search}%")
            | Product.english_name.ilike(f"%{search}%")
        )
    if attendance_status:
        clauses.append(Product.attendance_status == attendance_status)
    if employment_type:
        clauses.append(Product.employment_type == employment_type)
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
    employment_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[Product]:
    if attendance_status and attendance_status not in _VALID_ATTENDANCE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="attendance_status must be checked_in or checked_out",
        )

    if employment_type and employment_type not in _VALID_EMPLOYMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="employment_type must be part_time or full_time",
        )

    clauses = _product_filters(
        product_type=product_type,
        is_active=is_active,
        search=search,
        attendance_status=attendance_status,
        employment_type=employment_type,
    )

    count_q = select(func.count()).select_from(Product)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(Product)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(Product.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductCreate, _admin: AdminOnly, db: DB) -> Product:
    existing = await db.execute(select(Product).where(Product.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Product code already exists")

    product = Product(**body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, body: ProductUpdate, _admin: AdminOnly, db: DB) -> Product:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = body.model_dump(exclude_unset=True)
    if "code" in update_data:
        dup = await db.execute(
            select(Product).where(Product.code == update_data["code"], Product.id != product_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Product code already exists")

    for field, value in update_data.items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
