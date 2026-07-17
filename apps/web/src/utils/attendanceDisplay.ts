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

/** Shift a YYYY-MM-DD date key by `deltaDays` in the attendance timezone. */
export function shiftDateKey(dateKey: string, deltaDays: number, timeZone = ATTENDANCE_TIMEZONE): string {
  const [year, month, day] = dateKey.split('-').map(Number)
  const anchor = zonedTimeToUtc(year, month, day, 12, 0, 0, 0, timeZone)

  anchor.setUTCDate(anchor.getUTCDate() + deltaDays)

  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(anchor)
}

/** Convert YYYY-MM-DD date keys in the attendance timezone to UTC ISO bounds for API filters. */
export function getDateRangeIso(
  dateFrom?: string | null,
  dateTo?: string | null,
  timeZone = ATTENDANCE_TIMEZONE,
): { date_from?: string; date_to?: string } {
  const result: { date_from?: string; date_to?: string } = {}

  if (dateFrom?.trim()) {
    const [year, month, day] = dateFrom.split('-').map(Number)

    result.date_from = zonedTimeToUtc(year, month, day, 0, 0, 0, 0, timeZone).toISOString()
  }
  if (dateTo?.trim()) {
    const [year, month, day] = dateTo.split('-').map(Number)

    result.date_to = zonedTimeToUtc(year, month, day, 23, 59, 59, 999, timeZone).toISOString()
  }

  return result
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
  if (Number.isNaN(d.getTime()))
    return '—'

  const date = d.toLocaleDateString('en-GB', { timeZone: ATTENDANCE_TIMEZONE })
  const time = d.toLocaleTimeString('en-GB', {
    timeZone: ATTENDANCE_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  return `${date} ${time}`
}

export function formatAttendanceTime(iso: string | null | undefined): string {
  if (!iso)
    return '—'

  const d = new Date(iso)
  if (Number.isNaN(d.getTime()))
    return '—'

  return d.toLocaleTimeString('en-GB', {
    timeZone: ATTENDANCE_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** Event `source` = auto_checkout (Day-end / Generate day-boundary). */
export function isAutoCheckoutSource(source: string | null | undefined): boolean {
  return (source ?? '').toLowerCase() === 'auto_checkout'
}

/**
 * Summary `attendance_notes` written by Day-end or Generate, e.g.
 * "Auto checkout at day boundary (23:59)" /
 * "Closed by day-boundary auto checkout (23:59)".
 */
export function isAutoCheckoutDayNotes(notes: string | null | undefined): boolean {
  if (!notes?.trim())
    return false

  return /auto\s*checkout|day[- ]boundary/i.test(notes)
}

/**
 * True when last out is the day-boundary 23:59.
 * Accepts Hong Kong 23:59 (current) and UTC 23:59 (legacy Day-end writes).
 */
export function isDayBoundaryCheckoutTime(iso: string | null | undefined): boolean {
  if (!iso)
    return false

  // Wall-clock in the ISO string (what Summaries table shows via slice)
  if (/T23:59/.test(iso))
    return true

  const d = new Date(iso)
  if (Number.isNaN(d.getTime()))
    return false

  if (d.getUTCHours() === 23 && d.getUTCMinutes() === 59)
    return true

  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: ATTENDANCE_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d)

  const hour = Number(parts.find(p => p.type === 'hour')?.value)
  const minute = Number(parts.find(p => p.type === 'minute')?.value)
  const normalizedHour = hour === 24 ? 0 : hour

  return normalizedHour === 23 && minute === 59
}

/** Summaries day closed by auto checkout (notes and/or 23:59 last out). */
export function isAutoCheckoutSummaryDay(s: {
  attendance_notes?: string | null
  last_check_out?: string | null
}): boolean {
  return isAutoCheckoutDayNotes(s.attendance_notes) || isDayBoundaryCheckoutTime(s.last_check_out)
}

export function eventSourceLabel(source: string | null | undefined): string {
  if (!source)
    return '—'
  if (isAutoCheckoutSource(source))
    return 'Auto checkout'
  if (source === 'scan')
    return 'Scan'
  if (source === 'manual')
    return 'Manual'

  return source.replaceAll('_', ' ')
}

export function eventSourceColor(source: string | null | undefined): string {
  if (isAutoCheckoutSource(source))
    return 'warning'
  if (source === 'scan')
    return 'primary'
  if (source === 'manual')
    return 'secondary'

  return 'default'
}

export interface LastAttendanceInfo {
  attendance_status: 'checked_in' | 'checked_out'
  last_event_at: string | null
  last_event_location?: string | null
}

/** Human-readable line for product list / QR cards. */
export function formatLastAttendance(
  p: LastAttendanceInfo,
  options?: { compact?: boolean },
): string {
  if (!p.last_event_at)
    return 'No scans yet'

  const when = formatAttendanceDateTime(p.last_event_at)
  const action = p.attendance_status === 'checked_in' ? 'Checked in' : 'Checked out'
  const where = p.last_event_location?.trim()
  if (where && !options?.compact)
    return `${action} · ${when} · ${where}`

  return `${action} · ${when}`
}
