"""
QR token service.

Security design:
- Tokens are HMAC-signed JWTs that embed the product id and the product's
  current `qr_token_version`.  They have no `exp` claim — the QR is meant
  to live on a printed badge / lock screen and toggle check-in/out on each
  scan.
- The signing key (QR_SECRET) is separate from the auth JWT key so a leaked
  auth token cannot forge QR tokens and vice-versa.
- Rotation: admins can call the refresh endpoint to bump `qr_token_version`
  on the product; any QR with the previous version becomes invalid
  immediately.  This is the path to use if a QR is lost or compromised.
- Replay / double-tap protection: the scan service applies a short debounce
  window per product, returning the existing event for rapid duplicate
  scans.  The token's `jti` is still stored on each event for audit.
"""

import uuid
from datetime import datetime, timezone

from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = "HS256"


def issue_qr_token(product_id: str, token_version: int) -> str:
    """Return a signed token tied to (product_id, token_version)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": product_id,
        "ver": token_version,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "type": "qr",
    }
    return jwt.encode(payload, settings.QR_SECRET, algorithm=_ALGORITHM)


def verify_qr_token(token: str) -> dict:
    """
    Verify signature and `type` claim.  Returns the decoded payload dict.

    Raises JWTError on any failure (bad signature, malformed, wrong type).
    Note: the caller must additionally verify that `ver` matches the
    product's current `qr_token_version`.
    """
    payload = jwt.decode(token, settings.QR_SECRET, algorithms=[_ALGORITHM])
    if payload.get("type") != "qr":
        raise JWTError("Not a QR token")
    if "sub" not in payload or "ver" not in payload:
        raise JWTError("QR token missing required claims")
    return payload
