export const ATTENDANCE_TIMEZONE = 'Asia/Hong_Kong'

interface ZonedParts {
  year: number
  month: number
  day: number
  hour: number
  minute: number
  second: number
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
  })
  const parts = formatter.formatToParts(date)
  const get = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find(p => p.type === type)?.value ?? 0)
  const hour = get('hour')
  return {
    year: get('year'),
    month: get('month'),
    day: get('day'),
    hour: hour === 24 ? 0 : hour,
    minute: get('minute'),
    second: get('second'),
  }
}

/** Convert a wall-clock time in `timeZone` to a UTC Date. */
function zonedTimeToUtc(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
  ms: number,
  timeZone: string,
): Date {
  let utcMs = Date.UTC(year, month - 1, day, hour, minute, second, ms)
  for (let i = 0; i < 3; i++) {
    const zoned = getZonedParts(new Date(utcMs), timeZone)
    const asUtc = Date.UTC(zoned.year, zoned.month - 1, zoned.day, zoned.hour, zoned.minute, zoned.second, ms)
    const desired = Date.UTC(year, month - 1, day, hour, minute, second, ms)
    utcMs += desired - asUtc
  }
  return new Date(utcMs)
}

/** Start/end of the current calendar day in the attendance timezone, as UTC ISO strings for API filters. */
export function getTodayRangeIso(timeZone = ATTENDANCE_TIMEZONE, now = new Date()) {
  const dateKey = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
  const [year, month, day] = dateKey.split('-').map(Number)
  return {
    dateKey,
    date_from: zonedTimeToUtc(year, month, day, 0, 0, 0, 0, timeZone).toISOString(),
    date_to: zonedTimeToUtc(year, month, day, 23, 59, 59, 999, timeZone).toISOString(),
  }
}

export function formatAttendanceDateLabel(
  date = new Date(),
  timeZone = ATTENDANCE_TIMEZONE,
  locale?: string | string[],
) {
  return new Intl.DateTimeFormat(locale, {
    timeZone,
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(date)
}

export function formatAttendanceDateTime(iso: string | null | undefined): string {
  if (!iso)
    return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

export function formatAttendanceTime(iso: string | null | undefined): string {
  if (!iso)
    return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export interface LastAttendanceInfo {
  attendance_status: 'checked_in' | 'checked_out'
  last_event_at: string | null
  last_event_location?: string | null
}

/** Human-readable line for product list / QR cards. */
export function formatLastAttendance(p: LastAttendanceInfo): string {
  if (!p.last_event_at)
    return 'No scans yet'

  const when = formatAttendanceDateTime(p.last_event_at)
  const action = p.attendance_status === 'checked_in' ? 'Checked in' : 'Checked out'
  const where = p.last_event_location?.trim()
  if (where)
    return `${action} · ${when} · ${where}`
  return `${action} · ${when}`
}
