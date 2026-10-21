import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_purchasing import InventoryCounter
from app.models.location import Location


async def allocate_doc_no(
    db: AsyncSession, *, location_id: uuid.UUID, doc_type: str
) -> str:
    """Allocate the next sequential document number for (location, doc_type).

    Row-locks the counter (created on first use via savepoint). Returns e.g.
    "PO-MK-000007" using the location code, or the first 8 chars of its id.
    Caller commits — the number is not reused on rollback, so call this only
    when the document is actually being created.
    """
    result = await db.execute(
        select(InventoryCounter)
        .where(
            InventoryCounter.location_id == location_id,
            InventoryCounter.doc_type == doc_type,
        )
        .with_for_update()
    )
    counter = result.scalar_one_or_none()
    if counter is None:
        counter = InventoryCounter(location_id=location_id, doc_type=doc_type, next_no=1)
        try:
            async with db.begin_nested():
                db.add(counter)
                await db.flush()
        except IntegrityError:
            result = await db.execute(
                select(InventoryCounter)
                .where(
                    InventoryCounter.location_id == location_id,
                    InventoryCounter.doc_type == doc_type,
                )
                .with_for_update()
            )
            counter = result.scalar_one()

    allocated = counter.next_no
    counter.next_no = allocated + 1
    await db.flush()

    location = await db.get(Location, location_id)
    loc_tag = (location.code or "").strip() or str(location_id)[:8]
    return f"{doc_type}-{loc_tag}-{allocated:06d}"
