/**
 * review-format.ts
 *
 * Shared formatting & type-guard utilities extracted from Review.vue.
 *
 * WHY this file exists:
 *   Review.vue contained ~15 small helper functions mixed in with business logic.
 *   By pulling pure formatting functions here we:
 *     1. Make them independently testable.
 *     2. Let other components reuse them (e.g. export/print views).
 *     3. Shrink Review.vue so it only has orchestration logic.
 */

// ────────────────────────────────────────────
// Generic type-guard helpers
// ────────────────────────────────────────────

/** Check whether a value is a non-null, non-array object (i.e. a plain record). */
export function isObjectLike(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val)
}

/** True when the value is an array or a plain object — i.e. not a primitive. */
export function isComplexValue(val: unknown): boolean {
  return Array.isArray(val) || isObjectLike(val)
}

// ────────────────────────────────────────────
// Label / key formatting
// ────────────────────────────────────────────

/**
 * Convert a snake_case key into a human-readable Title Case label.
 * e.g. "year_of_assessment" → "Year Of Assessment"
 */
export function formatKeyLabel(key: string): string {
  if (!key)
    return ''

  return key
    .replace(/_/g, ' ')
    .replace(/(?:^|\s)\S/g, c => c.toUpperCase())
}

// ────────────────────────────────────────────
// Value formatting
// ────────────────────────────────────────────

/**
 * Format a primitive value for display.
 * - null / undefined → empty string
 * - boolean → "Yes" / "No"
 * - NaN → "-"
 */
export function formatPrimitive(value: unknown): string {
  if (value === null || value === undefined)
    return ''
  if (typeof value === 'boolean')
    return value ? 'Yes' : 'No'
  if (typeof value === 'number')
    return Number.isNaN(value) ? '-' : String(value)

  const s = String(value).trim()
  return s === '' ? '' : s
}

/**
 * Format an amount for display:
 *   - Adds thousands comma separators
 *   - Wraps negative numbers in parentheses: (1,234)
 */
export function formatAmount(val: unknown): string {
  if (val === null || val === undefined || val === '')
    return ''
  const s = String(val).trim().replace(/,/g, '')
  const num = Number(s)
  if (Number.isNaN(num))
    return String(val)
  const abs = Math.abs(num)
  const withCommas = abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return num < 0 ? `(${withCommas})` : withCommas
}

/**
 * Stringify any value for display — used in the clipboard copy builder.
 * Objects/arrays are JSON-stringified; primitives returned as-is.
 */
export function formatValue(v: unknown): string {
  if (v === null)
    return 'null'
  if (v === undefined)
    return 'undefined'
  if (typeof v === 'string')
    return v
  if (typeof v === 'number' || typeof v === 'boolean')
    return String(v)

  try {
    return JSON.stringify(v)
  }
  catch {
    return String(v)
  }
}

/**
 * Convert a number to a Roman numeral string (e.g. 1 → "I", 4 → "IV").
 * Used for tax schedule numbering.
 */
export function toRoman(n: number): string {
  const map: [number, string][] = [
    [10, 'X'], [9, 'IX'], [5, 'V'], [4, 'IV'], [1, 'I'],
  ]
  let num = Math.max(0, Math.floor(n))
  let out = ''
  for (const [val, sym] of map) {
    while (num >= val) {
      out += sym
      num -= val
    }
  }
  return out || String(n)
}

// ────────────────────────────────────────────
// KeyValueRow — shared display model
// ────────────────────────────────────────────

/**
 * A universal key-value row used throughout the Review screen.
 * Every section (basic info, client data, tax additional, tax schedules)
 * normalises its data into this shape so the template can render them uniformly.
 */
export interface KeyValueRow {
  key: string
  label: string
  value: unknown
}

/** Build an array of KeyValueRows from a plain object's own entries. */
export function buildRowsFromObject(obj: Record<string, unknown>): KeyValueRow[] {
  return Object.entries(obj).map(([key, value]) => ({
    key,
    label: formatKeyLabel(key),
    value,
  }))
}

/**
 * Turn an array or plain object into KeyValueRows.
 * Arrays get labels like "Item 1", "Item 2", …
 * Objects use their own keys (via buildRowsFromObject).
 */
export function entriesOf(val: unknown, labelPrefix = 'Item'): KeyValueRow[] {
  if (Array.isArray(val)) {
    return val.map((item, index) => ({
      key: String(index),
      label: `${labelPrefix} ${index + 1}`,
      value: item,
    }))
  }

  if (isObjectLike(val))
    return buildRowsFromObject(val)

  return []
}
