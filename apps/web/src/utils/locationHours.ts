import type { LocationItem } from '@/api/attendance/locations'

export const LOCATION_DAYS = [
  { key: 'mon', label: 'Monday', short: 'Mon' },
  { key: 'tue', label: 'Tuesday', short: 'Tue' },
  { key: 'wed', label: 'Wednesday', short: 'Wed' },
  { key: 'thu', label: 'Thursday', short: 'Thu' },
  { key: 'fri', label: 'Friday', short: 'Fri' },
  { key: 'sat', label: 'Saturday', short: 'Sat' },
  { key: 'sun', label: 'Sunday', short: 'Sun' },
] as const

export type HoursPreset = 'weekday' | 'sixday' | 'allday' | 'clear'

export interface DaySchedule {
  key: string
  label: string
  short: string
  isOpen: boolean
  openTime: string
  closeTime: string
}

export interface HoursScheduleEntry {
  day: string
  isOpen: boolean
  openTime: string
  closeTime: string
}

const DAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const

export function defaultHoursSchedule(): DaySchedule[] {
  return LOCATION_DAYS.map(d => ({
    ...d,
    isOpen: ['mon', 'tue', 'wed', 'thu', 'fri'].includes(d.key),
    openTime: '09:00',
    closeTime: '18:00',
  }))
}

export function applyHoursPreset(schedule: DaySchedule[], preset: HoursPreset) {
  schedule.forEach((d) => {
    if (preset === 'clear') {
      d.isOpen = false
    }
    else if (preset === 'weekday') {
      d.isOpen = ['mon', 'tue', 'wed', 'thu', 'fri'].includes(d.key)
      if (d.isOpen) {
        d.openTime = '09:00'
        d.closeTime = '18:00'
      }
    }
    else if (preset === 'sixday') {
      d.isOpen = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat'].includes(d.key)
      if (d.isOpen) {
        d.openTime = '09:00'
        d.closeTime = '18:00'
      }
    }
    else if (preset === 'allday') {
      d.isOpen = true
      d.openTime = '09:00'
      d.closeTime = '18:00'
    }
  })
}

export function buildBusinessHoursString(schedule: DaySchedule[]): string {
  const open = schedule.filter(d => d.isOpen)
  if (!open.length)
    return ''

  return open.map(d => `${d.short} ${d.openTime}–${d.closeTime}`).join(' · ')
}

export function loadHoursSchedule(rawDetails: Record<string, unknown> | null): DaySchedule[] {
  const stored = rawDetails?.hours_schedule as HoursScheduleEntry[] | undefined
  if (stored?.length) {
    return LOCATION_DAYS.map((d) => {
      const saved = stored.find(s => s.day === d.key)

      return {
        ...d,
        isOpen: saved?.isOpen ?? false,
        openTime: saved?.openTime ?? '09:00',
        closeTime: saved?.closeTime ?? '18:00',
      }
    })
  }

  return defaultHoursSchedule()
}

export function hoursScheduleToPayload(schedule: DaySchedule[]): HoursScheduleEntry[] {
  return schedule.map(d => ({
    day: d.key,
    isOpen: d.isOpen,
    openTime: d.openTime,
    closeTime: d.closeTime,
  }))
}

function compressDayRange(dayKeys: string[]): string {
  const sorted = [...new Set(dayKeys)].sort(
    (a, b) => DAY_ORDER.indexOf(a as typeof DAY_ORDER[number]) - DAY_ORDER.indexOf(b as typeof DAY_ORDER[number]),
  )
  const joined = sorted.join(',')

  if (joined === 'mon,tue,wed,thu,fri,sat,sun')
    return 'Daily'
  if (joined === 'mon,tue,wed,thu,fri')
    return 'Mon–Fri'
  if (joined === 'mon,tue,wed,thu,fri,sat')
    return 'Mon–Sat'

  return sorted.map(k => LOCATION_DAYS.find(d => d.key === k)?.short ?? k).join(', ')
}

/** Short one-line summary for location cards. */
export function formatCardBusinessHours(l: LocationItem): string {
  const rawSchedule = l.details?.hours_schedule
  const schedule = Array.isArray(rawSchedule) ? rawSchedule as HoursScheduleEntry[] : undefined

  if (schedule?.length) {
    const open = schedule.filter(s => s.isOpen)
    if (!open.length)
      return ''

    const first = open[0]
    const sameHours = open.every(s => s.openTime === first.openTime && s.closeTime === first.closeTime)

    if (sameHours)
      return `${compressDayRange(open.map(s => s.day))} ${first.openTime}–${first.closeTime}`

    const preview = open.slice(0, 2).map((s) => {
      const short = LOCATION_DAYS.find(d => d.key === s.day)?.short ?? s.day

      return `${short} ${s.openTime}–${s.closeTime}`
    }).join(' · ')

    return open.length > 2 ? `${preview}…` : preview
  }

  const raw = l.business_hours?.trim()
  if (!raw)
    return ''

  const parts = raw.split(' · ')
  if (parts.length <= 2)
    return raw

  const timePattern = /\d{2}:\d{2}[–-]\d{2}:\d{2}$/
  const times = parts.map(p => p.match(timePattern)?.[0]).filter(Boolean)

  if (times.length === parts.length && new Set(times).size === 1) {
    if (parts.length === 7)
      return `Daily ${times[0]}`
    if (parts.length === 5)
      return `Mon–Fri ${times[0]}`
    if (parts.length === 6)
      return `Mon–Sat ${times[0]}`

    return `${parts.length} days · ${times[0]}`
  }

  return `${parts[0]} · ${parts[1]}…`
}

export function showCardIcon(l: LocationItem): boolean {
  return !!l.icon_url && l.icon_url !== l.main_photo_url
}

export function cardCoverUrl(l: LocationItem): string | null {
  return l.main_photo_url || l.icon_url || null
}
