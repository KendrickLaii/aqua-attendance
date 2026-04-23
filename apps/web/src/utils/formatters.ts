/**
 * Format a number with comma separators for display.
 * e.g. 2000000 → "2,000,000"
 */
export const formatNumber = (value: string | number) => {
  const num = Number(value)
  if (isNaN(num)) return value
  return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}
