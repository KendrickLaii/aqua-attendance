from datetime import date

from fastapi import APIRouter, status

from app.deps import AdminOnly, DB
from app.services.auto_checkout import auto_checkout_for_date, get_still_checked_in_count

router = APIRouter(prefix="/auto-checkout", tags=["auto-checkout"])


@router.post("/run", status_code=status.HTTP_200_OK)
async def trigger_auto_checkout(admin: AdminOnly, db: DB, target_date: date | None = None) -> dict:
    """Manually trigger auto-checkout for a date (defaults to today).

    Normally run by a scheduled job at 23:59; this endpoint allows
    admins to force-run it for testing or backfill.
    """
    events = await auto_checkout_for_date(db, target_date=target_date)
    return {
        "target_date": str(target_date or "today"),
        "created_events": len(events),
        "message": f"Auto-checkout created {len(events)} events",
    }


@router.get("/status")
async def auto_checkout_status(_admin: AdminOnly, db: DB) -> dict:
    """Return the number of products still checked in (pending auto-checkout)."""
    count = await get_still_checked_in_count(db)
    return {"still_checked_in_count": count}
