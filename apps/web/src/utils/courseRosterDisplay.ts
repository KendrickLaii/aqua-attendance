import type { BillingUnit, CourseEnrollment, CourseSku, EnrollmentPurchase, Weekday } from '../api/attendance/courses'

export const billingUnitOptions: { title: string; value: BillingUnit }[] = [
  { title: 'Monthly (月費)', value: 'monthly' },
  { title: 'Per session (堂費)', value: 'per_session' },
]

export const weekdayOptions: { title: string; value: Weekday }[] = [
  { title: 'Mon', value: 'monday' },
  { title: 'Tue', value: 'tuesday' },
  { title: 'Wed', value: 'wednesday' },
  { title: 'Thu', value: 'thursday' },
  { title: 'Fri', value: 'friday' },
  { title: 'Sat', value: 'saturday' },
  { title: 'Sun', value: 'sunday' },
]

export function meetingDaysLabel(days: Weekday[] | null | undefined): string {
  if (!days?.length)
    return '—'
  const titles = weekdayOptions.filter(d => days.includes(d.value)).map(d => d.title)

  return titles.join('/')
}

export function formatRosterDate(value: string | null | undefined, empty = '—'): string {
  if (!value)
    return empty

  return String(value).slice(0, 10)
}

export function emptyToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim()

  return trimmed || null
}

export function rosterPriceLabel(sku: Pick<CourseSku, 'price' | 'billing_unit'>): string {
  if (sku.price == null)
    return 'No price — Generate will skip this class'
  const amount = `HK$${Number(sku.price).toFixed(2)}`

  return sku.billing_unit === 'per_session' ? `${amount} / session` : `${amount} / month`
}

export function skuBillingPreview(billingUnit: BillingUnit, price: number | null): string {
  const hasPrice = price != null && !Number.isNaN(Number(price))
  const priceText = hasPrice ? `HK$${Number(price).toFixed(2)}` : 'no price (Generate skips this class)'
  if (billingUnit === 'per_session')
    return `Bills ${priceText} × sessions purchased, once, when the student is enrolled. Not affected by attendance.`

  return `Bills ${priceText} once for each overlapping month. Class days are shown on the roster only.`
}

export function purchaseSummary(e: Pick<CourseEnrollment, 'purchases'>) {
  const purchases = e.purchases ?? []
  const unbilled = purchases.filter(p => p.billed_invoice_line_id === null)

  return {
    total: purchases.reduce((sum, p) => sum + p.purchased_quantity, 0),
    unbilledQty: unbilled.reduce((sum, p) => sum + p.purchased_quantity, 0),
  }
}

export function sortedPurchases(e: Pick<CourseEnrollment, 'purchases'>): EnrollmentPurchase[] {
  return [...(e.purchases ?? [])].sort((a, b) => a.purchased_at.localeCompare(b.purchased_at))
}

export function enrollmentStatusLabel(status: string): string {
  if (status === 'active')
    return 'In class'
  if (status === 'completed')
    return 'Left'
  if (status === 'cancelled')
    return 'Left'

  return status
}

export function billingWindowLabel(enrollment: Pick<CourseEnrollment, 'start_date' | 'end_date'>): string {
  return `${formatRosterDate(enrollment.start_date, 'Already started')} → ${formatRosterDate(enrollment.end_date, 'Ongoing')}`
}

/** Last day of the month after the current end. Same enrollment, one more billed month. */
export function renewEndDate(currentEnd: string): string {
  const [yearText, monthText] = currentEnd.slice(0, 10).split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const nextMonth = month === 12 ? 1 : month + 1
  const nextYear = month === 12 ? year + 1 : year
  const lastDay = new Date(nextYear, nextMonth, 0).getDate()

  return `${nextYear}-${String(nextMonth).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
}

/** Last calendar day of the month containing `isoDate`. Used to end an ongoing enrollment. */
export function lastDayOfMonth(isoDate: string): string {
  const [yearText, monthText] = isoDate.slice(0, 10).split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const lastDay = new Date(year, month, 0).getDate()

  return `${yearText}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
}

export function todayIsoDate(now = new Date()): string {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')

  return `${year}-${month}-${day}`
}

export function enrollmentPriceParts(
  enrollment: Pick<CourseEnrollment, 'unit_price'>,
  sku: Pick<CourseSku, 'price' | 'billing_unit'> | null,
): { amount: string; hint: string } | null {
  if (enrollment.unit_price != null) {
    return {
      amount: `HK$${Number(enrollment.unit_price).toFixed(2)}`,
      hint: 'this student',
    }
  }
  if (sku?.price != null) {
    return {
      amount: `HK$${Number(sku.price).toFixed(2)}`,
      hint: sku.billing_unit === 'per_session' ? 'class / session' : 'class / month',
    }
  }

  return null
}

export function studentLabel(
  unitId: string,
  enrollment?: Pick<CourseEnrollment, 'unit_name'>,
  studentById: Record<string, { full_name?: string }> = {},
): string {
  return enrollment?.unit_name || studentById[unitId]?.full_name || '…'
}

export function studentCode(
  unitId: string,
  enrollment?: Pick<CourseEnrollment, 'unit_code'>,
  studentById: Record<string, { code?: string }> = {},
): string {
  return enrollment?.unit_code || studentById[unitId]?.code || ''
}

export function matchesRosterSearch(
  enrollment: Pick<CourseEnrollment, 'unit_id' | 'unit_name' | 'unit_code'>,
  query: string,
  studentById: Record<string, { full_name?: string; code?: string }> = {},
): boolean {
  const q = query.trim().toLowerCase()
  if (!q)
    return true
  const name = (enrollment.unit_name || studentById[enrollment.unit_id]?.full_name || '').toLowerCase()
  const code = (enrollment.unit_code || studentById[enrollment.unit_id]?.code || '').toLowerCase()

  return name.includes(q) || code.includes(q)
}

export function enrollPriceHint(sku: Pick<CourseSku, 'price' | 'billing_unit'> | null): string {
  if (!sku)
    return ''
  if (sku.price == null)
    return '呢班未有價錢。請填呢個學生嘅月費，否則 Generate 會跳過。'

  const amount = `HK$${Number(sku.price).toFixed(2)}`

  return sku.billing_unit === 'per_session'
    ? `留空就用呢班嘅堂費（${amount}）。`
    : `留空就用呢班嘅月費（${amount}）。`
}

export function enrollBillPreview(input: {
  sku: Pick<CourseSku, 'billing_unit' | 'price'> | null
  unitPrice: number | null
  purchasedQuantity: number | null
}): string {
  const sku = input.sku
  if (!sku)
    return ''
  const price = input.unitPrice ?? sku.price ?? null
  if (sku.billing_unit === 'per_session') {
    const qty = input.purchasedQuantity
    if (qty == null || qty <= 0)
      return ''
    if (sku.price != null)
      return `${qty} session${qty === 1 ? '' : 's'} recorded — bill it from the Manual invoice (default HK$${sku.price.toFixed(2)}/session, adjustable when issuing).`

    return `${qty} session${qty === 1 ? '' : 's'} recorded — set the price when you issue the manual invoice.`
  }
  if (price == null)
    return 'No class price — this student will be skipped at Generate until a price is set.'

  return `Bills HK$${price.toFixed(2)} every month that overlaps the billed window.`
}

/** Reasons that are just field prompts — the button title still carries them. */
const FIELD_PROMPT_REASONS = new Set([
  'Search and pick a student.',
  'Enter how many sessions this student bought.',
  'Enter how many sessions to add.',
])

export function isFieldPromptReason(reason: string): boolean {
  return FIELD_PROMPT_REASONS.has(reason)
}

export function enrollDisabledReason(input: {
  skuId: string | null
  sku: Pick<CourseSku, 'is_active' | 'billing_unit'> | null
  atCapacity: boolean
  studentId: string | null
  activeUnitIds: Set<string>
  purchasedQuantity: number | null
  startDate?: string | null
  existingStart?: string | null
}): string {
  if (!input.skuId)
    return 'Pick a class first.'
  if (input.sku?.is_active === false)
    return 'This class is inactive — Generate skips it.'
  if (!input.studentId)
    return 'Search and pick a student.'
  if (input.studentId && input.activeUnitIds.has(input.studentId)) {
    // Already in class: the form tops up (per_session) or updates the window
    // (monthly) instead of joining, and takes no new seat.
    if (input.sku?.billing_unit === 'per_session') {
      if (!input.purchasedQuantity)
        return 'Enter how many sessions to add.'
      if (input.startDate && input.existingStart && input.startDate < input.existingStart)
        return `Start date can't be before this student's current start (${formatRosterDate(input.existingStart)}).`
    }

    return ''
  }
  if (input.atCapacity)
    return 'This class is full.'
  if (input.sku?.billing_unit === 'per_session' && !input.purchasedQuantity)
    return 'Enter how many sessions this student bought.'

  return ''
}

export function existingEnrollmentStatus(
  sku: Pick<CourseSku, 'billing_unit'> | null,
  enrollment: Pick<CourseEnrollment, 'purchases' | 'start_date' | 'end_date'> | null,
  formEnd: string | null,
): string {
  if (!sku || !enrollment)
    return ''
  const window = billingWindowLabel(enrollment)
  if (sku.billing_unit === 'per_session') {
    let suffix = ''
    if (enrollment.end_date && formEnd) {
      if (formEnd > enrollment.end_date)
        suffix = ` · extends to ${formEnd}`
      else if (formEnd < enrollment.end_date)
        suffix = ' · end not shortened (use Edit)'
    }

    return `In class · ${purchaseSummary(enrollment).total} sessions · ${window}${suffix}`
  }

  return `In class · ${window} · Update replaces this window`
}

export function rosterMetaLine(input: {
  sku: Pick<CourseSku, 'schedule_note' | 'meeting_weekdays' | 'staff_id' | 'location_id' | 'billing_unit' | 'price'>
  staffName: string
  locationName: string
}): string {
  const { sku } = input

  return [
    sku.schedule_note,
    sku.meeting_weekdays?.length ? meetingDaysLabel(sku.meeting_weekdays) : '',
    input.staffName,
    sku.location_id ? input.locationName : '',
    `${sku.billing_unit === 'per_session' ? '堂費' : '月費'} · ${rosterPriceLabel(sku)}`,
  ].filter(Boolean).join(' · ')
}
