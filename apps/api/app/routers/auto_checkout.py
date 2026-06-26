import uuid
from datetime import date

from fastapi import APIRouter, Body, status
from pydantic import BaseModel

from app.deps import AdminOnly, DB
from app.services.auto_checkout import auto_checkout_for_date, get_still_checked_in_count

router = APIRouter(prefix="/auto-checkout", tags=["auto-checkout"])


class AutoCheckoutRequest(BaseModel):
    target_date: date | None = None
    product_ids: list[uuid.UUID] | None = None


@router.post("/run", status_code=status.HTTP_200_OK)
async def trigger_auto_checkout(
    admin: AdminOnly,
    db: DB,
    payload: AutoCheckoutRequest = Body(default_factory=AutoCheckoutRequest),
) -> dict:
    """Manually trigger auto-checkout for a date (defaults to today).

    Normally run by a scheduled job at 23:59; this endpoint allows
    admins to force-run it for testing or backfill.

    When ``product_ids`` is provided, only those still-checked-in products
    are checked out. Unselected products stay checked in so admins can
    investigate why they never scanned out.
    """
    events = await auto_checkout_for_date(
        db, target_date=payload.target_date, product_ids=payload.product_ids
    )
    return {
        "target_date": str(payload.target_date or "today"),
        "created_events": len(events),
        "message": f"Auto-checkout created {len(events)} events",
    }


@router.get("/status")
async def auto_checkout_status(_admin: AdminOnly, db: DB) -> dict:
    """Return the number of products still checked in (pending auto-checkout)."""
    count = await get_still_checked_in_count(db)
    return {"still_checked_in_count": count}
