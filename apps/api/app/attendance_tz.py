"""Attendance calendar timezone (Hong Kong).

Must stay aligned with web ``ATTENDANCE_TIMEZONE`` in
``apps/web/src/utils/attendanceDisplay.ts``.

Naive datetimes from SQLite / legacy rows are treated as UTC, then converted.
"""

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

ATTENDANCE_TZ = ZoneInfo("Asia/Hong_Kong")


def attendance_today() -> date:
    """Calendar date in the attendance timezone."""
    return datetime.now(ATTENDANCE_TZ).date()


def as_utc(dt: datetime) -> datetime:
    """Coerce to UTC; naive values are treated as already-UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def as_attendance_tz(dt: datetime) -> datetime:
    """Convert to Asia/Hong_Kong (naive = UTC first)."""
    return as_utc(dt).astimezone(ATTENDANCE_TZ)


def attendance_date(dt: datetime) -> date:
    """Local attendance calendar date for an event timestamp."""
    return as_attendance_tz(dt).date()


def is_same_attendance_day(a: datetime, b: datetime) -> bool:
    """True when both timestamps fall on the same Hong Kong calendar day."""
    return attendance_date(a) == attendance_date(b)


def day_boundary_at(target_date: date, tzinfo=None) -> datetime:
    """Return 23:59:00 on ``target_date`` in the attendance timezone."""
    return datetime.combine(target_date, time(23, 59, 0), tzinfo=tzinfo or ATTENDANCE_TZ)
