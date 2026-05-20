from pydantic import BaseModel


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class QRPayload(BaseModel):
    """Returned to client so they can display it as a QR code.

    The token does not expire on its own; it is invalidated only when the
    product's `qr_token_version` is bumped via the refresh endpoint.
    `token_version` is included so clients can detect rotation.
    """

    qr_token: str
    token_version: int
