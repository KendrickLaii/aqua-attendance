import type { Shift } from '@/api/attendance/shifts'

export type ShiftTimes = Pick<Shift, 'unit_id' | 'shift_date' | 'start_time' | 'end_time'> & { id?: string }

export interface ShiftStaffLike {
  id: string
  is_active: boolean
  registered_location_id: string
  scan_location_ids: string[]
}

/** Deep tones so white text stays readable on solid shift blocks; amber pairs with dark text. */
export const SHIFT_COLORS = [
  '#2E7D32',
  '#1565C0',
  '#6A1B9A',
  '#BF360C',
  '#C62828',
  '#00695C',
  '#5D4037',
  '#455A64',
  '#F9A825',
] as const

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const pad = (n: number) => String(n).padStart(2, '0')

/** Local calendar date as YYYY-MM-DD (no UTC shift). */
export function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function parseIsoDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)

  return new Date(y, m - 1, d)
}

export function addDays(iso: string, days: number): string {
  const d = parseIsoDate(iso)

  d.setDate(d.getDate() + days)

  return toIsoDate(d)
}

/** Monday of the week containing `d` (weeks start on Monday). */
export function mondayOf(d: Date): string {
  const offset = (d.getDay() + 6) % 7

  return addDays(toIsoDate(d), -offset)
}

export function weekDates(mondayIso: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(mondayIso, i))
}

export function formatDayHeader(iso: string): { weekday: string; day: string } {
  const d = parseIsoDate(iso)

  return { weekday: WEEKDAYS[d.getDay()], day: `${d.getDate()} ${MONTHS[d.getMonth()]}` }
}

export function formatWeekRange(mondayIso: string): string {
  const start = parseIsoDate(mondayIso)
  const end = parseIsoDate(addDays(mondayIso, 6))

  const startLabel = start.getFullYear() === end.getFullYear()
    ? `${start.getDate()} ${MONTHS[start.getMonth()]}`
    : `${start.getDate()} ${MONTHS[start.getMonth()]} ${start.getFullYear()}`

  return `${startLabel} – ${end.getDate()} ${MONTHS[end.getMonth()]} ${end.getFullYear()}`
}

/** "09:00:00" -> "09:00". */
export function hhmm(time: string): string {
  return time.slice(0, 5)
}

export function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)

  return h * 60 + m
}

export function shiftMinutes(shift: Pick<Shift, 'start_time' | 'end_time'>): number {
  return Math.max(0, timeToMinutes(shift.end_time) - timeToMinutes(shift.start_time))
}

export function formatShiftHours(minutes: number): string {
  return `${Number((minutes / 60).toFixed(2))}h`
}

export function totalMinutes(shifts: Pick<Shift, 'start_time' | 'end_time'>[]): number {
  return shifts.reduce((sum, s) => sum + shiftMinutes(s), 0)
}

function overlaps(a: ShiftTimes, b: ShiftTimes): boolean {
  return a.unit_id === b.unit_id
    && a.shift_date === b.shift_date
    && timeToMinutes(a.start_time) < timeToMinutes(b.end_time)
    && timeToMinutes(b.start_time) < timeToMinutes(a.end_time)
}

/** Existing shifts that clash with `candidate` (same staff, same day, times intersect). Skips itself by id. */
export function findOverlaps<T extends ShiftTimes>(candidate: ShiftTimes, shifts: T[]): T[] {
  return shifts.filter(s => (!candidate.id || s.id !== candidate.id) && overlaps(candidate, s))
}

export function overlappingShiftIds(shifts: Shift[]): Set<string> {
  const ids = new Set<string>()
  for (let i = 0; i < shifts.length; i++) {
    for (let j = i + 1; j < shifts.length; j++) {
      if (overlaps(shifts[i], shifts[j])) {
        ids.add(shifts[i].id)
        ids.add(shifts[j].id)
      }
    }
  }

  return ids
}

export function cellKey(unitId: string, isoDate: string): string {
  return `${unitId}|${isoDate}`
}

export function groupShiftsByCell(shifts: Shift[]): Map<string, Shift[]> {
  const map = new Map<string, Shift[]>()
  for (const s of [...shifts].sort((a, b) => a.start_time.localeCompare(b.start_time))) {
    const key = cellKey(s.unit_id, s.shift_date)

    map.set(key, [...(map.get(key) ?? []), s])
  }

  return map
}

/**
 * Rows for the week grid: active staff who belong to (or can scan at) the location,
 * plus anyone — even inactive — who already has a shift in `shifts`.
 */
export function staffRowsForLocation<T extends ShiftStaffLike>(
  staff: T[],
  shifts: Pick<Shift, 'unit_id'>[],
  locationId: string | null,
): T[] {
  const withShifts = new Set(shifts.map(s => s.unit_id))

  return staff.filter(u => withShifts.has(u.id) || (u.is_active && (
    !locationId
    || u.registered_location_id === locationId
    || u.scan_location_ids.includes(locationId)
  )))
}

/** Dark or light text for a "#RRGGBB" background (WCAG relative luminance). */
export function readableTextColor(hex: string): string {
  const channel = (i: number) => {
    const c = Number.parseInt(hex.slice(i, i + 2), 16) / 255

    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }

  const luminance = 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)

  // White wins when its contrast ratio beats black's: (1.05)/(L+0.05) > (L+0.05)/0.05
  return luminance < 0.179 ? '#FFFFFF' : 'rgba(0, 0, 0, 0.87)'
}

/** "Chan Tai Man" -> "CT"; "陳大文" -> "陳". */
export function staffInitials(name: string): string {
  const trimmed = name.trim()
  if (!trimmed)
    return '?'
  if (/^[\u3400-\u9FFF]/.test(trimmed))
    return trimmed[0]

  return trimmed.split(/\s+/).slice(0, 2).map(w => w[0]!.toUpperCase()).join('')
}

/** Stable palette colour per id, so the same person keeps the same avatar colour. */
export function avatarColor(id: string): string {
  let hash = 0
  for (const ch of id)
    hash = (hash * 31 + ch.charCodeAt(0)) >>> 0

  return SHIFT_COLORS[hash % SHIFT_COLORS.length]
}

export function isWeekend(iso: string): boolean {
  const day = parseIsoDate(iso).getDay()

  return day === 0 || day === 6
}

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** "2026-09" -> every date in September 2026. */
export function monthDates(month: string): string[] {
  const [y, m] = month.split('-').map(Number)
  const days = new Date(y, m, 0).getDate()

  return Array.from({ length: days }, (_, i) => `${month}-${pad(i + 1)}`)
}

export function formatMonthLabel(month: string): string {
  const [y, m] = month.split('-').map(Number)

  return `${MONTH_NAMES[m - 1]} ${y}`
}

/** Month that owns a week — the one containing its Thursday (ISO-8601 rule). */
export function monthOfWeek(mondayIso: string): string {
  return addDays(mondayIso, 3).slice(0, 7)
}

/** `count` months starting `before` months ahead of `month`, as { value: 'YYYY-MM', title }. */
export function monthOptions(month: string, before = 6, count = 12): { value: string; title: string }[] {
  const [y, m] = month.split('-').map(Number)

  return Array.from({ length: count }, (_, i) => {
    const d = new Date(y, m - 1 - before + i, 1)
    const value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}`

    return { value, title: formatMonthLabel(value) }
  })
}

/** Parse a `?week=` query value into a Monday, falling back to this week. */
export function weekFromQuery(value: unknown, now = new Date()): string {
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const d = parseIsoDate(value)
    if (!Number.isNaN(d.getTime()))
      return mondayOf(d)
  }

  return mondayOf(now)
}

function csvCell(value: string | number): string {
  const text = String(value)

  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export interface ShiftCsvRow {
  date: string
  staffName: string
  staffCode: string
  locationName: string
  shift: Pick<Shift, 'start_time' | 'end_time' | 'title' | 'notes'>
}

/** UTF-8 BOM so Excel opens Chinese names correctly. */
export function buildShiftCsv(rows: ShiftCsvRow[]): string {
  const header = ['Date', 'Weekday', 'Staff', 'Code', 'Location', 'Start', 'End', 'Hours', 'Shift', 'Notes']

  const lines = rows.map(r => [
    r.date,
    formatDayHeader(r.date).weekday,
    r.staffName,
    r.staffCode,
    r.locationName,
    hhmm(r.shift.start_time),
    hhmm(r.shift.end_time),
    Number((shiftMinutes(r.shift) / 60).toFixed(2)),
    r.shift.title ?? '',
    r.shift.notes ?? '',
  ].map(csvCell).join(','))

  return `\uFEFF${[header.join(','), ...lines].join('\r\n')}\r\n`
}
