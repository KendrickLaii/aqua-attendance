import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, AdminOnly
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(
    _admin: AdminOnly,
    db: DB,
    product_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[Product]:
    q = select(Product)
    if product_type:
        q = q.where(Product.product_type == product_type)
    if is_active is not None:
        q = q.where(Product.is_active == is_active)
    if search:
        q = q.where(
            Product.code.ilike(f"%{search}%")
            | Product.full_name.ilike(f"%{search}%")
            | Product.english_name.ilike(f"%{search}%")
        )
    q = q.order_by(Product.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
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
