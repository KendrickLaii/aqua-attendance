from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str | None = None


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class QRPayload(BaseModel):
    """Returned to client so they can display it as a QR code.

    The token does not expire on its own; it is invalidated only when the
    unit's `qr_token_version` is bumped via the refresh endpoint.
    `token_version` is included so clients can detect rotation.
    """

    qr_token: str
    token_version: int
