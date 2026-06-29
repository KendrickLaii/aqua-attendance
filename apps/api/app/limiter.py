"""Shared rate limiter instance for FastAPI endpoints.

Uses a Redis storage backend when ``REDIS_URL`` is configured so limits are
counted correctly across multiple API replicas. Without it, slowapi falls back
to in-memory storage which only counts within a single process.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

_limiter_kwargs: dict = {"key_func": get_remote_address}
if settings.REDIS_URL:
    _limiter_kwargs["storage_uri"] = settings.REDIS_URL

limiter = Limiter(**_limiter_kwargs)
