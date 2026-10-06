import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.location_attachment import LocationAttachment
from app.services.media_storage import delete_attachment_file

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_HK = timezone(timedelta(hours=8))


def current_month() -> str:
    return f"{datetime.now(_HK):%Y-%m}"


def earliest_month() -> str:
    """Oldest month still retained (current month counts as the first of N)."""
    now = datetime.now(_HK)
    index = now.year * 12 + (now.month - 1) - (settings.ATTACHMENT_RETENTION_MONTHS - 1)
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def is_valid_month(month: str) -> bool:
    return bool(_MONTH_RE.match(month))


def month_in_window(month: str) -> bool:
    return is_valid_month(month) and earliest_month() <= month <= current_month()


async def purge_expired_attachments(db: AsyncSession) -> int:
    """Delete rows + files for months older than the retention window."""
    cutoff = earliest_month()
    rows = (
        await db.execute(
            select(LocationAttachment.id, LocationAttachment.file_key).where(LocationAttachment.month < cutoff)
        )
    ).all()
    if not rows:
        return 0
    await db.execute(delete(LocationAttachment).where(LocationAttachment.id.in_([r.id for r in rows])))
    await db.commit()
    for row in rows:
        delete_attachment_file(row.file_key)
    return len(rows)
