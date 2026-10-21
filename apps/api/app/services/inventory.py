import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem, InventoryMovement, InventoryStock
from app.models.user import User

OUT_REASON_CODES = {
    "damage", "loss", "gift", "sample", "internal_use", "supplier_return", "sale", "other",
}
IN_REASON_CODES = {"opening", "sales_return", "other"}
REASON_CODES_REQUIRING_NOTE = {"damage", "loss", "gift"}

VALID_TYPES = {"in", "out", "adjust", "transfer_in", "transfer_out"}


async def _locked_stock(db: AsyncSession, item_id: uuid.UUID, location_id: uuid.UUID) -> InventoryStock:
    result = await db.execute(
        select(InventoryStock)
        .where(InventoryStock.item_id == item_id, InventoryStock.location_id == location_id)
        .with_for_update()
    )
    stock = result.scalar_one_or_none()
    if stock:
        return stock
    stock = InventoryStock(item_id=item_id, location_id=location_id, quantity=0)
    try:
        async with db.begin_nested():
            db.add(stock)
            await db.flush()
    except IntegrityError:
        result = await db.execute(
            select(InventoryStock)
            .where(InventoryStock.item_id == item_id, InventoryStock.location_id == location_id)
            .with_for_update()
        )
        stock = result.scalar_one()
    return stock


def _validate_reason_code(type: str, reason_code: str | None, reason: str | None) -> None:
    if reason_code is None:
        return
    allowed = {"out": OUT_REASON_CODES, "in": IN_REASON_CODES}.get(type)
    if allowed is None or reason_code not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"reason_code '{reason_code}' is not valid for movement type '{type}'",
        )
    if reason_code in REASON_CODES_REQUIRING_NOTE and not (reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail=f"reason is required when reason_code is '{reason_code}'",
        )


async def apply_movement(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    location_id: uuid.UUID,
    type: str,
    quantity: int,
    reason: str | None,
    reference: str | None,
    user: User | None,
    reason_code: str | None = None,
    item: InventoryItem | None = None,
) -> InventoryMovement:
    """The ONLY entry point that changes stock. Locks the stock row, rejects a
    negative resulting balance, and appends a ledger row with balance_after.

    For 'adjust', ``quantity`` is the new absolute on-hand count; the delta is
    computed against the locked balance. ``reference`` is unique — a repeat of
    the same reference returns the already-recorded movement (idempotent).
    'out' and 'transfer_out' may not push quantity below the reserved amount;
    'adjust' may not set the count below it either (cancel or ship the orders
    holding the reservations first). For 'out', ``unit_cost`` snapshots the
    item's avg_cost. Caller commits.
    """
    if type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"unsupported movement type: {type}")
    _validate_reason_code(type, reason_code, reason)

    if reference:
        existing = await db.execute(
            select(InventoryMovement).where(InventoryMovement.reference == reference)
        )
        movement = existing.scalar_one_or_none()
        if movement:
            if movement.item_id != item_id or movement.location_id != location_id or movement.type != type:
                raise HTTPException(
                    status_code=409,
                    detail="reference already used by a different movement",
                )
            return movement

    stock = await _locked_stock(db, item_id, location_id)

    if type in ("in", "transfer_in"):
        delta = quantity
    elif type in ("out", "transfer_out"):
        delta = -quantity
    else:
        delta = quantity - stock.quantity

    balance_after = stock.quantity + delta
    if balance_after < 0:
        raise HTTPException(
            status_code=422,
            detail=f"insufficient stock: have {stock.quantity}, need {-delta}",
        )
    if type in ("out", "transfer_out") and balance_after < stock.reserved:
        raise HTTPException(
            status_code=422,
            detail=f"cannot go below reserved: {stock.reserved} reserved, {stock.quantity} on hand",
        )
    if type == "adjust" and balance_after < stock.reserved:
        raise HTTPException(
            status_code=422,
            detail=(
                f"count {balance_after} is below reserved {stock.reserved}; "
                "cancel or ship the sales orders holding reservations first"
            ),
        )

    unit_cost = None
    if type == "out":
        if item is None:
            item = await db.get(InventoryItem, item_id)
        unit_cost = float(item.avg_cost) if item else None

    prev_quantity = stock.quantity
    stock.quantity = balance_after
    movement = InventoryMovement(
        item_id=item_id,
        location_id=location_id,
        type=type,
        quantity_delta=delta,
        balance_after=balance_after,
        reason=reason,
        reason_code=reason_code,
        unit_cost=unit_cost,
        reference=reference,
        created_by=user.id if user else None,
    )
    db.add(movement)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Concurrent duplicate of the same unique reference: roll back our
        # stock mutation (the savepoint undid the flush, not the ORM state)
        # and return the winner.
        stock.quantity = prev_quantity
        if reference:
            existing = await db.execute(
                select(InventoryMovement).where(InventoryMovement.reference == reference)
            )
            movement = existing.scalar_one_or_none()
            if movement is not None:
                return movement
        raise
    return movement


async def reserve(
    db: AsyncSession, *, item_id: uuid.UUID, location_id: uuid.UUID, quantity: int
) -> InventoryStock:
    """Reserve ``quantity`` units (e.g. confirmed sales order). Caller commits."""
    stock = await _locked_stock(db, item_id, location_id)
    if stock.reserved + quantity > stock.quantity:
        raise HTTPException(
            status_code=422,
            detail=f"cannot reserve {quantity}: only {stock.quantity - stock.reserved} available",
        )
    stock.reserved += quantity
    await db.flush()
    return stock


async def release(
    db: AsyncSession, *, item_id: uuid.UUID, location_id: uuid.UUID, quantity: int
) -> InventoryStock:
    """Release previously reserved units. Caller commits."""
    stock = await _locked_stock(db, item_id, location_id)
    if quantity > stock.reserved:
        raise HTTPException(
            status_code=422,
            detail=f"cannot release {quantity}: only {stock.reserved} reserved",
        )
    stock.reserved -= quantity
    await db.flush()
    return stock


async def transfer(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    from_location_id: uuid.UUID,
    to_location_id: uuid.UUID,
    quantity: int,
    reason: str | None,
    user: User | None,
) -> tuple[InventoryMovement, InventoryMovement]:
    """Move stock between locations: transfer_out + transfer_in in one call
    (one transaction — the caller commits). Same location is rejected.
    """
    if from_location_id == to_location_id:
        raise HTTPException(status_code=422, detail="from and to locations must differ")

    for loc_id in sorted((from_location_id, to_location_id), key=str):
        await _locked_stock(db, item_id, loc_id)

    transfer_id = uuid.uuid4()
    out_movement = await apply_movement(
        db,
        item_id=item_id,
        location_id=from_location_id,
        type="transfer_out",
        quantity=quantity,
        reason=reason,
        reference=f"TRF:{transfer_id}:out",
        user=user,
    )
    in_movement = await apply_movement(
        db,
        item_id=item_id,
        location_id=to_location_id,
        type="transfer_in",
        quantity=quantity,
        reason=reason,
        reference=f"TRF:{transfer_id}:in",
        user=user,
    )
    return out_movement, in_movement
