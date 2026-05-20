import uuid
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, AdminOnly, CurrentUser
from app.models.attendance import AttendanceEvent
from app.models.product import Product
from app.schemas.attendance import AttendanceOut, ManualCorrectionRequest, ScanRequest
from app.services import attendance as att_svc
from app.services.qr import verify_qr_token

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _event_to_out(event: AttendanceEvent) -> AttendanceOut:
    return AttendanceOut(
        id=event.id,
        product_id=event.product_id,
        product_code=event.product.code if event.product else None,
        product_name=event.product.full_name if event.product else None,
        product_type=event.product.product_type if event.product else None,
        event_type=event.event_type,
        recorded_at=event.recorded_at,
        attendance_status=event.product.attendance_status if event.product else None,
        qr_jti=event.qr_jti,
        recorded_by_user_id=event.recorded_by_user_id,
        client_device_id=event.client_device_id,
        notes=event.notes,
    )


async def _reload_with_product(db, event_id: uuid.UUID) -> AttendanceEvent:
    result = await db.execute(
        select(AttendanceEvent)
        .options(selectinload(AttendanceEvent.product))
        .where(AttendanceEvent.id == event_id)
    )
    return result.scalar_one()


@router.post("/scan", response_model=AttendanceOut)
async def scan(body: ScanRequest, user: CurrentUser, db: DB) -> AttendanceOut:
    """Scan a product's QR.

    The same QR toggles check-in / check-out on each scan based on the
    product's current `attendance_status`.  Rapid duplicate scans within
    `SCAN_DEBOUNCE_SECONDS` return the existing event (no duplicate row).
    """
    try:
        payload = verify_qr_token(body.qr_token)
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid QR: {e}")

    try:
        target_product_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR: bad subject")

    result = await db.execute(select(Product).where(Product.id == target_product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is inactive")

    if payload.get("ver") != product.qr_token_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR: token has been rotated, please refresh the QR",
        )

    event, _created = await att_svc.record_scan(
        db,
        product=product,
        jti=payload.get("jti"),
        recorded_by_user_id=user.id,
        device_id=body.device_id,
    )

    event = await _reload_with_product(db, event.id)
    return _event_to_out(event)


@router.get("", response_model=list[AttendanceOut])
async def list_attendance(
    _user: CurrentUser,
    db: DB,
    product_id: uuid.UUID | None = None,
    product_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    event_type: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[AttendanceOut]:
    """List attendance events. Any authenticated admin can view all records."""
    events, _total = await att_svc.list_events(
        db,
        product_id=product_id,
        product_type=product_type,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        page=page,
        page_size=page_size,
    )
    return [_event_to_out(e) for e in events]


@router.post("/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_manual_correction(
    body: ManualCorrectionRequest, admin: AdminOnly, db: DB
) -> AttendanceOut:
    result = await db.execute(select(Product).where(Product.id == body.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    event = await att_svc.manual_correction(
        db,
        product=product,
        event_type=body.event_type.value if hasattr(body.event_type, 'value') else body.event_type,
        recorded_at=body.recorded_at,
        notes=body.notes,
        recorded_by_user_id=admin.id,
    )
    event = await _reload_with_product(db, event.id)
    return _event_to_out(event)


@router.get("/export/csv")
async def export_csv(
    _admin: AdminOnly,
    db: DB,
    product_id: uuid.UUID | None = None,
    product_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> StreamingResponse:
    events, _ = await att_svc.list_events(
        db,
        product_id=product_id,
        product_type=product_type,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=10000,
    )
    buf = StringIO()
    buf.write("id,product_id,product_code,product_name,product_type,event_type,recorded_at,recorded_by_user_id,device_id,notes\n")
    for e in events:
        pcode = e.product.code if e.product else ""
        pname = e.product.full_name if e.product else ""
        ptype = e.product.product_type if e.product else ""
        buf.write(
            f"{e.id},{e.product_id},{pcode},{pname},{ptype},{e.event_type},"
            f"{e.recorded_at.isoformat()},{e.recorded_by_user_id or ''},{e.client_device_id or ''},{e.notes or ''}\n"
        )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_export.csv"},
    )
