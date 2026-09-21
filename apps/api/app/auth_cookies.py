"""HttpOnly auth cookies for the web app. Mobile still uses JSON body tokens."""

from fastapi import Response

from app.config import settings

ACCESS_COOKIE = "attendance_access"
REFRESH_COOKIE = "attendance_refresh"
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
