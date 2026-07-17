/** Must match web ATTENDANCE_TIMEZONE and API ATTENDANCE_TZ. */
export const ATTENDANCE_TIMEZONE = 'Asia/Hong_Kong';

interface ZonedParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

function getZonedParts(date: Date, timeZone: string): ZonedParts {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  const parts = formatter.formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((p) => p.type === type)?.value ?? 0);
  const hour = get('hour');
  return {
    year: get('year'),
    month: get('month'),
    day: get('day'),
    hour: hour === 24 ? 0 : hour,
    minute: get('minute'),
    second: get('second'),
  };
}

function zonedTimeToUtc(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
  ms: number,
  timeZone: string
): Date {
  let utcMs = Date.UTC(year, month - 1, day, hour, minute, second, ms);
  for (let i = 0; i < 3; i++) {
    const zoned = getZonedParts(new Date(utcMs), timeZone);
    const asUtc = Date.UTC(
      zoned.year,
      zoned.month - 1,
      zoned.day,
      zoned.hour,
      zoned.minute,
      zoned.second,
      ms
    );
    const desired = Date.UTC(year, month - 1, day, hour, minute, second, ms);
    utcMs += desired - asUtc;
  }
  return new Date(utcMs);
}

export function getAttendanceDateKey(
  date = new Date(),
  timeZone = ATTENDANCE_TIMEZONE
): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

export function shiftAttendanceDateKey(
  dateKey: string,
  deltaDays: number,
  timeZone = ATTENDANCE_TIMEZONE
): string {
  const [year, month, day] = dateKey.split('-').map(Number);
  const anchor = zonedTimeToUtc(year, month, day, 12, 0, 0, 0, timeZone);
  anchor.setUTCDate(anchor.getUTCDate() + deltaDays);
  return getAttendanceDateKey(anchor, timeZone);
}

/** UTC ISO bounds for a Hong Kong calendar day range (API filters). */
export function getAttendanceDateRangeIso(
  dateFromKey: string,
  dateToKey: string,
  timeZone = ATTENDANCE_TIMEZONE
): { date_from: string; date_to: string } {
  const [fy, fm, fd] = dateFromKey.split('-').map(Number);
  const [ty, tm, td] = dateToKey.split('-').map(Number);
  return {
    date_from: zonedTimeToUtc(fy, fm, fd, 0, 0, 0, 0, timeZone).toISOString(),
    date_to: zonedTimeToUtc(ty, tm, td, 23, 59, 59, 999, timeZone).toISOString(),
  };
}

export function formatAttendanceDateTime(
  iso: string,
  locale?: string,
  timeZone = ATTENDANCE_TIMEZONE
): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString(locale, { timeZone }),
    time: d.toLocaleTimeString(locale, {
      timeZone,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }),
  };
}
