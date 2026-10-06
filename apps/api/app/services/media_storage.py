from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.config import settings

_OPTIMIZE_MIN_BYTES = 300 * 1024

ATTACHMENT_PREFIX = "_attachments/"
_KEY_RE = re.compile(r"^\d{4}/\d{2}/[0-9a-f]{32}\.(png|jpg|gif|webp)$")
_ATTACHMENT_KEY_RE = re.compile(r"^_attachments/\d{4}/\d{2}/[0-9a-f]{32}\.(png|jpg|gif|webp)$")


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


def optimize_image(content: bytes, content_type: str, ext: str) -> tuple[bytes, str, str]:
    """Downscale/recompress large photos. Returns the input unchanged when
    it is already small, animated (GIF), undecodable, or would not shrink."""
    if content_type == "image/gif":
        return content, content_type, ext
    max_dim = settings.UPLOAD_MAX_DIMENSION
    try:
        img = Image.open(BytesIO(content))
        img.load()
        img = ImageOps.exif_transpose(img)
    except Exception:
        return content, content_type, ext

    oversized = max(img.size) > max_dim
    if not oversized and len(content) <= _OPTIMIZE_MIN_BYTES:
        return content, content_type, ext

    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    out = BytesIO()
    if has_alpha:
        img.convert("RGBA").save(out, "PNG", optimize=True)
        new_type, new_ext = "image/png", ".png"
    else:
        img.convert("RGB").save(out, "JPEG", quality=settings.UPLOAD_JPEG_QUALITY, optimize=True)
        new_type, new_ext = "image/jpeg", ".jpg"

    result = out.getvalue()
    if not oversized and len(result) >= len(content):
        return content, content_type, ext
    return result, new_type, new_ext


def _store(content: bytes, subdir: str = "") -> SavedMedia:
    if not content:
        raise MediaStorageError("File is empty")
    if len(content) > settings.UPLOAD_MAX_BYTES:
        raise MediaStorageError("File exceeds size limit")

    content_type, ext = sniff_image(content)
    content, content_type, ext = optimize_image(content, content_type, ext)
    now = datetime.now(timezone.utc)
    key = f"{subdir}{now:%Y}/{now:%m}/{uuid.uuid4().hex}{ext}"
    dest = _upload_root() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return SavedMedia(
        key=key,
        url=f"/api/uploads/{key}",
        content_type=content_type,
        size=len(content),
    )


def save_bytes(content: bytes) -> SavedMedia:
    return _store(content)


def save_attachment_bytes(content: bytes) -> SavedMedia:
    """Private storage: keys live under _attachments/ and are never served by the public /uploads route."""
    return _store(content, ATTACHMENT_PREFIX)


def resolve_attachment_path(key: str) -> Path:
    if ".." in key.split("/") or not _ATTACHMENT_KEY_RE.match(key):
        raise MediaStorageError("Invalid attachment key")
    path = (_upload_root() / key).resolve()
    if not path.is_file():
        raise FileNotFoundError(key)
    return path


def delete_attachment_file(key: str) -> None:
    try:
        resolve_attachment_path(key).unlink(missing_ok=True)
    except (MediaStorageError, FileNotFoundError):
        pass


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
