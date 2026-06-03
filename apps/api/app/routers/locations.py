import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.deps import AdminOnly, DB
from app.models.attendance import AttendanceEvent
from app.models.location import Location
from app.models.product import Product, product_scan_locations
from app.schemas.location import LocationCreate, LocationOut, LocationUpdate
from app.utils.search import ilike_contains

router = APIRouter(prefix="/locations", tags=["locations"])


def _normalize_location_names(data: dict) -> dict:
    """DB requires name_zh NOT NULL; UI treats English as required and Chinese optional."""
    name_en = data.get("name_en")
    name_zh = data.get("name_zh")
    if not name_zh or (isinstance(name_zh, str) and not name_zh.strip()):
        if name_en:
            data["name_zh"] = name_en.strip() if isinstance(name_en, str) else name_en
    return data


@router.get("", response_model=list[LocationOut])
async def list_locations(
    _admin: AdminOnly,
    db: DB,
    response: Response,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
) -> list[Location]:
    clauses = []
    if is_active is not None:
        clauses.append(Location.is_active == is_active)
    if search:
        clauses.append(
            or_(
                ilike_contains(Location.name_zh, search),
                ilike_contains(Location.name_en, search),
                ilike_contains(Location.code, search),
                ilike_contains(Location.region, search),
                ilike_contains(Location.location_type, search),
            )
        )

    count_q = select(func.count()).select_from(Location)
    if clauses:
        count_q = count_q.where(*clauses)
    total = await db.scalar(count_q) or 0

    q = select(Location)
    if clauses:
        q = q.where(*clauses)
    q = q.order_by(Location.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(body: LocationCreate, _admin: AdminOnly, db: DB) -> Location:
    if body.code:
        exists = await db.execute(select(Location).where(Location.code == body.code))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Location code already exists")
    data = _normalize_location_names(body.model_dump())
    location = Location(**data)
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


@router.get("/{location_id}", response_model=LocationOut)
async def get_location(location_id: uuid.UUID, _admin: AdminOnly, db: DB) -> Location:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.patch("/{location_id}", response_model=LocationOut)
async def update_location(location_id: uuid.UUID, body: LocationUpdate, _admin: AdminOnly, db: DB) -> Location:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    update_data = body.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code:
        exists = await db.execute(select(Location).where(Location.code == new_code, Location.id != location_id))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Location code already exists")

    for field, value in update_data.items():
        setattr(location, field, value)

    merged = {
        "name_en": location.name_en,
        "name_zh": location.name_zh,
    }
    normalized = _normalize_location_names(merged)
    location.name_zh = normalized["name_zh"]

    await db.commit()
    await db.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(location_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(select(Location).where(Location.id == location_id))
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    used_in_events = await db.execute(select(AttendanceEvent.id).where(AttendanceEvent.location_id == location_id).limit(1))
    used_in_products = await db.execute(select(Product.id).where(Product.last_event_location_id == location_id).limit(1))
    used_as_registered = await db.execute(
        select(Product.id).where(Product.registered_location_id == location_id).limit(1)
    )
    used_in_scan = await db.execute(
        select(product_scan_locations.c.product_id)
        .where(product_scan_locations.c.location_id == location_id)
        .limit(1)
    )
    if (
        used_in_events.scalar_one_or_none()
        or used_in_products.scalar_one_or_none()
        or used_as_registered.scalar_one_or_none()
        or used_in_scan.first()
    ):
        raise HTTPException(
            status_code=409,
            detail="Location is referenced by products or attendance records. Set it inactive instead of deleting.",
        )

    await db.delete(location)
    await db.commit()
