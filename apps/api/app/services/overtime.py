"""OT (overtime) calculation service.

Rules (from DATABASE_CHANGES.md):
- 15-minute time slots, rounded (<7.5min down, >=7.5min up)
- OT = work beyond location.business_hours.close
- Work hours = first check_in + last check_out of the day
- Lunch break is fixed and deducted at service layer
"""

from datetime import date, datetime, time, timedelta
from typing import NamedTuple

from app.models.location import Location


class TimeSlot(NamedTuple):
    hours: int
    minutes: int

    def to_float(self) -> float:
        return self.hours + self.minutes / 60


class WorkDayResult(NamedTuple):
    total_slots: int          # 15-min slots
    ot_slots: int             # overtime 15-min slots
    total_hours: float
    ot_hours: float
    standard_hours: float


_SLOTS_PER_HOUR = 4  # 60 / 15
_SLOT_MINUTES = 15
_ROUND_THRESHOLD = _SLOT_MINUTES / 2  # 7.5 minutes


def _round_to_15(dt: datetime) -> datetime:
    """Round a datetime to the nearest 15-minute slot."""
    minute = dt.minute
    second = dt.second
    microsecond = dt.microsecond
    total_minutes = minute + second / 60 + microsecond / 60_000_000

    slots = int(total_minutes // _SLOT_MINUTES)
    remainder = total_minutes % _SLOT_MINUTES

    if remainder >= _ROUND_THRESHOLD:
        slots += 1

    rounded_minute = slots * _SLOT_MINUTES
    if rounded_minute >= 60:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return dt.replace(minute=rounded_minute, second=0, microsecond=0)


def _parse_time(t_str: str) -> time:
    """Parse 'HH:MM' to time object."""
    h, m = map(int, t_str.split(":"))
    return time(h, m)


def _location_close_time(
    location: Location | None,
    target_date: date,
) -> time | None:
    """Extract closing time from location.business_hours JSON."""
    if location is None or location.business_hours is None:
        return None

    weekday = target_date.strftime("%a").lower()  # mon, tue, ...
    hours = location.business_hours
    if isinstance(hours, dict):
        day_hours = hours.get(weekday) or hours.get(weekday[:3])
        if day_hours and isinstance(day_hours, dict):
            close_str = day_hours.get("close")
            if close_str:
                return _parse_time(close_str)
    return None


def _minutes_between(start: datetime, end: datetime) -> int:
    """Total minutes between two datetimes."""
    delta = end - start
    return int(delta.total_seconds() // 60)


def calculate_workday(
    first_check_in: datetime,
    last_check_out: datetime,
    location: Location | None = None,
    target_date: date | None = None,
    lunch_minutes: int = 60,
) -> WorkDayResult:
    """Calculate workday metrics from first check-in and last check-out.

    Args:
        first_check_in: datetime of the first check-in of the day
        last_check_out: datetime of the last check-out of the day
        location: optional Location to determine closing time for OT
        target_date: the date being calculated (defaults to first_check_in.date)
        lunch_minutes: fixed lunch break deduction (default 60)

    Returns:
        WorkDayResult with slot-based hours
    """
    if target_date is None:
        target_date = first_check_in.date()

    # Round to 15-min slots
    rounded_in = _round_to_15(first_check_in)
    rounded_out = _round_to_15(last_check_out)

    if rounded_out <= rounded_in:
        return WorkDayResult(0, 0, 0.0, 0.0, 0.0)

    total_minutes = _minutes_between(rounded_in, rounded_out)

    # Deduct lunch
    work_minutes = max(0, total_minutes - lunch_minutes)
    total_slots = work_minutes // _SLOT_MINUTES
    total_hours = total_slots / _SLOTS_PER_HOUR

    # Determine standard hours from location closing time
    close_time = _location_close_time(location, target_date)
    if close_time:
        # Standard = from check-in time to location close time (minus lunch)
        close_dt = datetime.combine(target_date, close_time)
        if close_time.hour < 6:  # e.g. 02:00 next day
            close_dt += timedelta(days=1)

        standard_minutes_raw = _minutes_between(rounded_in, close_dt)
        standard_minutes = max(0, standard_minutes_raw - lunch_minutes)
        standard_slots = standard_minutes // _SLOT_MINUTES
        standard_hours = standard_slots / _SLOTS_PER_HOUR

        ot_slots = max(0, total_slots - standard_slots)
        ot_hours = ot_slots / _SLOTS_PER_HOUR
    else:
        # No location hours configured — everything is standard
        standard_hours = total_hours
        ot_slots = 0
        ot_hours = 0.0

    return WorkDayResult(
        total_slots=total_slots,
        ot_slots=ot_slots,
        total_hours=round(total_hours, 2),
        ot_hours=round(ot_hours, 2),
        standard_hours=round(standard_hours, 2),
    )
