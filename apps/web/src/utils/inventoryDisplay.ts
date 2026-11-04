const hkdFormatter = new Intl.NumberFormat('en-HK', {
  style: 'currency',
  currency: 'HKD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** `HK$1,234.50`; `—` when the value is missing. */
export function formatMoney(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '')
    return '—'

  const n = Number(value)

  return Number.isFinite(n) ? hkdFormatter.format(n) : '—'
}
