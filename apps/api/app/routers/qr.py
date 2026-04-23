from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas.auth import QRPayload
from app.services.qr import issue_qr_token

router = APIRouter(prefix="/qr", tags=["qr"])


@router.get("/token", response_model=QRPayload)
async def get_qr_token(user: CurrentUser) -> dict:
    """Issue a short-lived signed QR token for the authenticated user."""
    token, lifetime = issue_qr_token(str(user.id))
    return {"qr_token": token, "expires_in": lifetime}
