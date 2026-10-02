"""HttpOnly auth cookies for the web app. Mobile still uses JSON body tokens."""

from fastapi import Response

from app.config import settings

ACCESS_COOKIE = "attendance_access"
REFRESH_COOKIE = "attendance_refresh"
STAFF_SHIFT_COOKIE = "staff_shift_access"
STAFF_SHIFT_COOKIE_MAX_AGE = 12 * 60 * 60
_COOKIE_PATH = "/api"


def _cookie_secure() -> bool:
    return settings.ENV.strip().lower() in ("production", "prod")


def set_auth_cookies(response: Response, tokens: dict) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=tokens["access_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=_COOKIE_PATH,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=tokens["refresh_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=_COOKIE_PATH,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path=_COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)


def set_staff_shift_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=STAFF_SHIFT_COOKIE,
        value=token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=STAFF_SHIFT_COOKIE_MAX_AGE,
        path=_COOKIE_PATH,
    )


def clear_staff_shift_cookie(response: Response) -> None:
    response.delete_cookie(STAFF_SHIFT_COOKIE, path=_COOKIE_PATH)
