import type { AttendanceSummary } from '@/api/attendance/summaries'
import { isAutoCheckoutSummaryDay } from '@/utils/attendanceDisplay'

export type DetailStatus = 'all' | 'complete' | 'needs_review' | 'incomplete' | 'weekend'

export interface DetailTotals {
  regular: number
  overtime: number
  regularSlots: number
  otSlots: number
  days: number
  autoCheckoutDays: number
  incompleteDays: number
  needsReviewDays: number

  /** Unreliable while incomplete / auto-checkout days are in the visible set */
  reliable: boolean
}

export const unitTypeOptions = [
  { title: 'All types', value: '' },
  { title: 'Staff', value: 'staff' },
  { title: 'Student', value: 'student' },
]

export const detailStatusOptions: { title: string; value: DetailStatus }[] = [
  { title: 'All', value: 'all' },
  { title: 'Complete', value: 'complete' },
  { title: 'Needs review', value: 'needs_review' },
  { title: 'Incomplete', value: 'incomplete' },
  { title: 'Weekend', value: 'weekend' },
]

const detailStatusFilterIconMap: Record<DetailStatus, string> = {
  all: 'ri-list-check',
  complete: 'ri-checkbox-circle-line',
  needs_review: 'ri-alarm-warning-line',
  incomplete: 'ri-error-warning-line',
  weekend: 'ri-calendar-2-line',
}

export function detailStatusFilterIcon(status: DetailStatus) {
  return detailStatusFilterIconMap[status] ?? 'ri-list-check'
}

export function needsManualReview(s: AttendanceSummary) {
  return !s.is_complete || isAutoCheckoutSummaryDay(s)
}

export function isMissingCheckIn(s: AttendanceSummary) {
  return !s.first_check_in && !!s.last_check_out
}

export function filterSummariesByDetailStatus(summaries: AttendanceSummary[], status: DetailStatus) {
  if (status === 'weekend')
    return summaries.filter(s => s.is_weekend)
  if (status === 'complete')
    return summaries.filter(s => s.is_complete && !isAutoCheckoutSummaryDay(s))
  if (status === 'needs_review')
    return summaries.filter(s => needsManualReview(s))
  if (status === 'incomplete')
    return summaries.filter(s => !s.is_complete)

  return summaries
}

export function computeDetailTotals(summaries: AttendanceSummary[]): DetailTotals {
  const regular = summaries.reduce((sum, s) => sum + safeNumber(s.regular_hours), 0)
  const overtime = summaries.reduce((sum, s) => sum + safeNumber(s.overtime_hours), 0)
  const regularSlots = summaries.reduce((sum, s) => sum + safeNumber(s.regular_slots), 0)
  const otSlots = summaries.reduce((sum, s) => sum + safeNumber(s.ot_slots), 0)
  const autoCheckoutDays = summaries.filter(s => isAutoCheckoutSummaryDay(s)).length
  const incompleteDays = summaries.filter(s => !s.is_complete).length
  const needsReviewDays = summaries.filter(s => needsManualReview(s)).length

  return {
    regular,
    overtime,
    regularSlots,
    otSlots,
    days: summaries.length,
    autoCheckoutDays,
    incompleteDays,
    needsReviewDays,
    reliable: needsReviewDays === 0,
  }
}

export function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

export function typeLabel(type: string) {
  return unitTypeOptions.find(o => o.value === type)?.title ?? type
}

export function summaryStatusLabel(s: AttendanceSummary) {
  if (s.is_holiday)
    return 'Holiday'
  if (s.is_weekend)
    return 'Weekend'
  if (isMissingCheckIn(s))
    return 'Incomplete'
  if (isAutoCheckoutSummaryDay(s))
    return 'Needs review'
  if (!s.is_complete)
    return 'Incomplete'

  return 'Complete'
}

export function summaryStatusIcon(s: AttendanceSummary) {
  if (s.is_holiday)
    return 'ri-calendar-event-line'
  if (s.is_weekend)
    return 'ri-calendar-2-line'
  if (isAutoCheckoutSummaryDay(s))
    return 'ri-alarm-warning-line'
  if (!s.is_complete)
    return 'ri-error-warning-line'

  return 'ri-checkbox-circle-line'
}

export function summaryStatusColor(s: AttendanceSummary) {
  if (s.is_holiday || s.is_weekend)
    return 'info'
  if (needsManualReview(s))
    return 'warning'

  return 'success'
}

export function formatHours(h: number) {
  return Number.isFinite(h) ? h.toFixed(2) : '-'
}

export function safeNumber(value: number) {
  return Number.isFinite(value) ? value : 0
}

export function formatDayHours(s: AttendanceSummary, hours: number) {
  if (!s.is_complete)
    return '—'

  return formatHours(hours)
}

export function formatDaySlots(s: AttendanceSummary, slots: number) {
  if (!s.is_complete)
    return '—'

  return String(slots)
}

export function formatTotalHours(hours: number, reliable: boolean) {
  if (!reliable)
    return '—'

  return formatHours(hours)
}

export function formatTotalSlots(slots: number, reliable: boolean) {
  if (!reliable)
    return '—'

  return String(slots)
}
