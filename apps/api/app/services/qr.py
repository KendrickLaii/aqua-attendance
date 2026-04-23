"""
QR token service.

Security design:
- Tokens are HMAC-signed JWTs with a short lifetime (default 60 s).
- Payload: { sub: user_id, jti: unique_id, iat, exp, type: "qr" }.
- The signing key (QR_SECRET) is separate from the auth JWT key so a leaked
  auth token cannot forge QR tokens and vice-versa.
- Clock skew tolerance: 5 seconds (jose default leeway).
- Replay prevention: the `jti` is recorded in the attendance_events table
  with a UNIQUE constraint.  A second scan of the same jti returns the
  original event (idempotent 200) rather than an error — but no duplicate
  row is created.
"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = "HS256"
_LEEWAY_SECONDS = 5


def issue_qr_token(user_id: str) -> tuple[str, int]:
    """Return (signed_token, lifetime_seconds)."""
    now = datetime.now(timezone.utc)
    lifetime = settings.QR_TOKEN_LIFETIME_SECONDS
    payload = {
        "sub": user_id,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=lifetime),
        "type": "qr",
    }
    token = jwt.encode(payload, settings.QR_SECRET, algorithm=_ALGORITHM)
    return token, lifetime


def verify_qr_token(token: str) -> dict:
    """
    Verify signature and expiry.  Returns the decoded payload dict.
    Raises JWTError on any failure (bad sig, expired, wrong type).
    """
    payload = jwt.decode(
        token,
        settings.QR_SECRET,
        algorithms=[_ALGORITHM],
        options={"leeway": _LEEWAY_SECONDS},
    )
    if payload.get("type") != "qr":
        raise JWTError("Not a QR token")
    return payload
