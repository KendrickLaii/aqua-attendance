import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.location import Location
from app.models.product import Product


async def fetch_active_locations(
    db: AsyncSession,
    location_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Location]:
    if not location_ids:
        return {}

    unique_ids = list(dict.fromkeys(location_ids))
    result = await db.execute(
        select(Location).where(Location.id.in_(unique_ids))
    )
    locations = {loc.id: loc for loc in result.scalars().all()}

    missing = [str(loc_id) for loc_id in unique_ids if loc_id not in locations]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location not found: {', '.join(missing)}",
        )

    inactive = [str(loc.id) for loc in locations.values() if not loc.is_active]
    if inactive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Location is inactive: {', '.join(inactive)}",
        )

    return locations


def validate_scan_location_ids(scan_location_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    unique_ids = list(dict.fromkeys(scan_location_ids))
    if not unique_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scan_location_ids must contain at least one location",
        )
    return unique_ids


async def resolve_product_locations(
    db: AsyncSession,
    *,
    registered_location_id: uuid.UUID,
    scan_location_ids: list[uuid.UUID],
) -> tuple[Location, list[Location]]:
    scan_ids = validate_scan_location_ids(scan_location_ids)
    lookup_ids = list(dict.fromkeys([registered_location_id, *scan_ids]))
    location_map = await fetch_active_locations(db, lookup_ids)
    registered = location_map[registered_location_id]
    scan_locs = [location_map[loc_id] for loc_id in scan_ids]
    return registered, scan_locs


async def replace_scan_locations(
    product: Product,
    scan_locations: list[Location],
) -> None:
    product.scan_locations = scan_locations


async def load_product_with_locations(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> Product | None:
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.registered_location),
            selectinload(Product.scan_locations),
            selectinload(Product.student_profile),
            selectinload(Product.staff_profile),
        )
        .where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


def product_allows_location(product: Product, location_id: uuid.UUID | None) -> bool:
    if location_id is None:
        return False
    return any(loc.id == location_id for loc in product.scan_locations)
