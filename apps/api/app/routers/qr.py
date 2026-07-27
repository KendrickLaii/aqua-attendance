import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, AdminOnly
from app.models.unit import Unit
from app.schemas.auth import QRPayload
from app.services import attendance as att_svc
from app.services.qr import issue_qr_token

router = APIRouter(prefix="/qr", tags=["qr"])


def _build_payload(unit: Unit) -> dict:
    token = issue_qr_token(str(unit.id), unit.qr_token_version)
    return {"qr_token": token, "token_version": unit.qr_token_version}


@router.get("/token/{unit_id}", response_model=QRPayload)
async def get_qr_token(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    """Return the current QR token for a unit.

    The token has no expiry — it stays valid until the unit's
    `qr_token_version` is bumped via the refresh endpoint.
    """
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if not unit.is_active:
        raise HTTPException(status_code=400, detail="Unit is inactive")
    return _build_payload(unit)


@router.post("/token/{unit_id}/refresh", response_model=QRPayload)
async def refresh_qr_token(unit_id: uuid.UUID, _admin: AdminOnly, db: DB) -> dict:
    """Rotate the unit's QR — invalidates any previously-issued QR.

    Use only when the existing QR has been lost or compromised; normal
    check-in / check-out does not need refresh.
    """
    result = await db.execute(select(Unit).where(Unit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if not unit.is_active:
        raise HTTPException(status_code=400, detail="Unit is inactive")
    unit = await att_svc.rotate_unit_qr(db, unit=unit)
    return _build_payload(unit)
