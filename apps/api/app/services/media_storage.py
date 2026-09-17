from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

_KEY_RE = re.compile(r"^\d{4}/\d{2}/[0-9a-f]{32}\.(png|jpg|gif|webp)$")


class MediaStorageError(ValueError):
    """Rejected upload or unsafe key."""


@dataclass(frozen=True)
class SavedMedia:
    key: str
    url: str
    content_type: str
    size: int


def sniff_image(content: bytes) -> tuple[str, str]:
    """Return (content_type, extension) from magic bytes."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif", ".gif"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise MediaStorageError("Only JPEG, PNG, WebP, and GIF images are allowed")


def _upload_root() -> Path:
    return Path(settings.UPLOAD_DIR).resolve()


def save_bytes(content: bytes) -> SavedMedia:
    if not content:
        raise MediaStorageError("File is empty")
    if len(content) > settings.UPLOAD_MAX_BYTES:
        raise MediaStorageError("File exceeds size limit")

    content_type, ext = sniff_image(content)
    now = datetime.now(timezone.utc)
    key = f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}{ext}"
    dest = _upload_root() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return SavedMedia(
        key=key,
        url=f"/api/uploads/{key}",
        content_type=content_type,
        size=len(content),
    )


def resolve_upload_path(key: str) -> Path:
    normalized = key.replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/") or not _KEY_RE.match(normalized):
        raise MediaStorageError("Invalid upload key")

    root = _upload_root()
    path = (root / normalized).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise MediaStorageError("Invalid upload key") from exc
    if not path.is_file():
        raise FileNotFoundError(normalized)
    return path


def content_type_for_key(key: str) -> str:
    suffix = Path(key).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
