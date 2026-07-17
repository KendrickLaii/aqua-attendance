/**
 * Shared YYYY-MM month picker state for Summaries / Payroll.
 * Month boundaries follow Asia/Hong_Kong (same as attendance day filters).
 */
import { getTodayRangeIso } from '@/utils/attendanceDisplay'

export function useYearMonth(initial = '') {
  const yearMonth = ref(initial)

  function toCurrentMonth() {
    const [year, month] = getTodayRangeIso().dateKey.split('-')

    yearMonth.value = `${year}-${month}`
  }

  const parsed = computed(() => {
    const ym = yearMonth.value
    if (!ym || !/^\d{4}-\d{2}$/.test(ym))
      return null

    const [year, month] = ym.split('-').map(Number)
    if (month < 1 || month > 12)
      return null

    return { year, month }
  })

  const monthDateRange = computed(() => {
    if (!parsed.value)
      return null

    const { year, month } = parsed.value
    const lastDay = new Date(year, month, 0).getDate()
    const pad = (n: number) => String(n).padStart(2, '0')

    return {
      date_from: `${year}-${pad(month)}-01`,
      date_to: `${year}-${pad(month)}-${pad(lastDay)}`,
    }
  })

  const monthLabel = computed(() => {
    if (!parsed.value)
      return yearMonth.value || 'Select a month'

    return new Date(parsed.value.year, parsed.value.month - 1, 1).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
    })
  })

  function changeMonth(delta: number) {
    if (!parsed.value)
      return

    const next = new Date(parsed.value.year, parsed.value.month - 1 + delta, 1)

    yearMonth.value = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
  }

  return {
    yearMonth,
    parsed,
    monthDateRange,
    monthLabel,
    changeMonth,
    toCurrentMonth,
  }
}
