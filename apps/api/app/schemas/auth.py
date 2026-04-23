from pydantic import BaseModel


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class QRPayload(BaseModel):
    """Returned to client so they can display it as a QR code."""
    qr_token: str
    expires_in: int
