import uuid
from datetime import date

from fastapi import APIRouter, Body, status
from pydantic import BaseModel

from app.attendance_tz import attendance_today
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
    """Manually trigger day-boundary auto-checkout for a date (defaults to today).

    There is **no** scheduled 23:59 job yet — production must call this
    endpoint (or an equivalent worker) on a schedule. Until then, admins
    use Dashboard Day-end checkout for testing / end-of-day backfill.

    When ``product_ids`` is provided, only those still-checked-in products
    are checked out. Unselected products stay checked in so admins can
    investigate why they never scanned out.

    After creating events, regenerates that month's attendance summaries
    so Incomplete days become Complete.
    """
    from app.services.summary_generator import generate_monthly_summaries

    events = await auto_checkout_for_date(
        db, target_date=payload.target_date, product_ids=payload.product_ids
    )
    target = payload.target_date or attendance_today()
    summaries = await generate_monthly_summaries(db, year=target.year, month=target.month)
    return {
        "target_date": str(target),
        "created_events": len(events),
        "summaries_created": summaries["created"],
        "summaries_updated": summaries["updated"],
        "message": (
            f"Auto-checkout created {len(events)} events; "
            f"summaries {summaries['created']} created / {summaries['updated']} updated"
        ),
    }


@router.get("/status")
async def auto_checkout_status(_admin: AdminOnly, db: DB) -> dict:
    """Return the number of products still checked in (pending auto-checkout)."""
    count = await get_still_checked_in_count(db)
    return {"still_checked_in_count": count}
