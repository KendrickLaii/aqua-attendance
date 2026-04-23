import { computed } from 'vue'
import type { Ref } from 'vue'
import { isObjectLike } from '@/utils/review-format'
import type { KeyValueRow } from '@/utils/review-format'

/**
 * useTaxComputationReview composable
 *
 * WHY this exists:
 *   Review.vue had ~200 lines of tax-computation mapping, filtering, and flattening logic.
 *   This composable isolates all of it so Review.vue only consumes the final computed results.
 *
 * WHAT it does:
 *   1. Maps raw `taxComputationData` (from the API) into a structured `TaxComputationMapped` shape.
 *   2. Provides `processedSchedules` — a computed list where each schedule's dataContentList
 *      has ALREADY been filtered/normalised (fixing the old bug where the template called the
 *      heavy `handleProfitsTaxComputationDataContent` function twice per schedule).
 *   3. Exports a `flattenTaxComputationData()` helper used by the clipboard-copy feature.
 *
 * KEY FIX — duplicated filtering:
 *   Previously, `handleProfitsTaxComputationDataContent()` contained the same row-filtering logic
 *   as `flattenTaxComputationData()`. Now both share `filterSelectedTableRows()`.
 */

// ────────────────────────────────────────────
// Types
// ────────────────────────────────────────────

export interface TaxComputationMapped {
  taxRate: string
  taxSchedules: TaxScheduleItem[]
}

export interface TaxScheduleItem {
  scheduleName: string
  scheduleNumber: number
  dataContentList: unknown[]
}

/** Normalised table row after filtering (used in both display and clipboard copy). */
export interface FilteredTableRow {
  name: unknown
  schedule: unknown
  amount: unknown
}

/** Processed content item — either a table or a set of selected checkboxes. */
export type ProcessedContentItem =
  | { type: 'table'; rows: FilteredTableRow[] }
  | { type: 'checkboxes'; selectedCheckbox: unknown[] }

/** A schedule with its dataContentList already processed for display. */
export interface ProcessedSchedule {
  scheduleName: string
  scheduleNumber: number
  /** The dataContentList after filtering — ready for the template to render directly. */
  processedContent: unknown[]
}

// ────────────────────────────────────────────
// Type guards (used by the template)
// ────────────────────────────────────────────

export function isTableContent(val: unknown): val is { type: 'table'; rows: Array<Record<string, unknown>> } {
  return isObjectLike(val)
    && (val as Record<string, unknown>).type === 'table'
    && Array.isArray((val as Record<string, unknown>).rows)
}

export function isCheckboxContent(val: unknown): val is { type: 'checkboxes'; selectedCheckbox: unknown[] } {
  return isObjectLike(val)
    && (val as Record<string, unknown>).type === 'checkboxes'
    && Array.isArray((val as Record<string, unknown>).selectedCheckbox)
}

export function isTaxScheduleEntry(entry: KeyValueRow): entry is KeyValueRow & { value: TaxScheduleItem } {
  if (!isObjectLike(entry.value))
    return false
  const v = entry.value as Record<string, unknown>
  return (
    typeof v.scheduleName === 'string'
    && typeof v.scheduleNumber === 'number'
    && Array.isArray(v.dataContentList)
  )
}

// ────────────────────────────────────────────
// Shared filtering helper
// ────────────────────────────────────────────

/**
 * filterSelectedTableRows — THE single source of truth for row filtering.
 *
 * Previously this logic was copy-pasted in two places:
 *   1. `handleProfitsTaxComputationDataContent()` (for display)
 *   2. `flattenTaxComputationData()` (for clipboard copy)
 *
 * Now both call this function, guaranteeing consistent behaviour.
 *
 * Rules:
 *   - Keep rows where `itemSelect === true`
 *   - Exclude rows with type "subtotal" or "blankRow"
 */
export function filterSelectedTableRows(tableData: unknown[]): Record<string, unknown>[] {
  return tableData.filter((r): r is Record<string, unknown> => {
    if (!r || typeof r !== 'object')
      return false
    const t = r as Record<string, unknown>
    return t.itemSelect === true
      && t.type !== 'subtotal'
      && t.type !== 'blankRow'
  })
}

// ────────────────────────────────────────────
// Internal helpers
// ────────────────────────────────────────────

const PROFITS_TAX_NAMES = ['Profits Tax Computation', 'ProfitsTaxComputation']

function isProfitsTaxSchedule(name: string): boolean {
  return PROFITS_TAX_NAMES.includes(name)
}

/**
 * Process a schedule's dataContentList for display.
 *
 * For the "Profits Tax Computation" schedule, this:
 *   - Extracts selected rows from `type: "info"` items → `{ type: 'table', rows }`
 *   - Extracts selected checkboxes from `type: "checkboxes"` items
 *
 * For all other schedules, the dataContentList is returned as-is.
 */
function processDataContent(scheduleName: string, dataContentList: unknown[]): unknown[] {
  if (!isProfitsTaxSchedule(scheduleName) || !Array.isArray(dataContentList))
    return dataContentList

  const out: ProcessedContentItem[] = []
  for (const item of dataContentList) {
    if (!item || typeof item !== 'object')
      continue
    const row = item as Record<string, unknown>
    const type = String(row.type ?? '')

    if (type === 'info') {
      const tableData = Array.isArray(row.tableData) ? row.tableData : []
      const filtered = filterSelectedTableRows(tableData)
      const rows: FilteredTableRow[] = filtered.map(t => ({
        name: t.name ?? '',
        schedule: t.schedule ?? '',
        amount: t.this ?? '',
      }))
      out.push({ type: 'table', rows })
    }
    else if (type === 'checkboxes') {
      const selectedCheckbox = Array.isArray(row.selectedCheckbox) ? row.selectedCheckbox : []
      out.push({ type: 'checkboxes', selectedCheckbox })
    }
  }
  return out
}

/**
 * Map the raw API response into a structured shape.
 *
 * Raw shape: { data: [...], taxMenu: [...], taxRate: number }
 *   - `data` contains schedule definitions (id, title, description, dataContentList)
 *   - `taxMenu` contains menu items that mark which schedules are included
 *   - `taxRate` is a decimal (e.g. 0.165 → "16.50%")
 *
 * We join taxMenu (included only) with data on the `analysis ↔ title` key
 * to produce the final taxSchedules array.
 */
function mapTaxComputationData(raw: unknown): TaxComputationMapped | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw))
    return null

  const obj = raw as Record<string, unknown>
  const data = Array.isArray(obj.data) ? obj.data : []
  const taxMenu = Array.isArray(obj.taxMenu) ? obj.taxMenu : []
  const taxRateNum = typeof obj.taxRate === 'number' ? obj.taxRate : 0

  // Only keep menu items that are marked as included
  const includedMenus = taxMenu.filter(
    (m: unknown) => typeof m === 'object' && m !== null && (m as Record<string, unknown>).isIncluded === true,
  )

  // Join each included menu item with its matching data entry (by title ↔ analysis)
  const taxSchedules: TaxScheduleItem[] = includedMenus.map((m: unknown) => {
    const menu = m as Record<string, unknown>
    const analysis = String(menu.analysis ?? '')
    const scheduleNumber = Number(menu.scheduleNumber)
    const dataItem = data.find(
      (d: unknown) => typeof d === 'object' && d !== null && (d as Record<string, unknown>).title === analysis,
    ) as Record<string, unknown> | undefined
    const dataContentList = Array.isArray(dataItem?.dataContentList) ? dataItem.dataContentList : []
    return {
      scheduleName: analysis,
      scheduleNumber: Number.isNaN(scheduleNumber) ? 0 : scheduleNumber,
      dataContentList,
    }
  })

  const taxRate = `${(taxRateNum * 100).toFixed(2)}%`

  return { taxRate, taxSchedules }
}

// ────────────────────────────────────────────
// Composable
// ────────────────────────────────────────────

export function useTaxComputationReview(taxComputationData: Ref<unknown>) {
  /**
   * The mapped tax computation data — null when there is nothing to display.
   * Reactively recomputed whenever the prop changes.
   */
  const taxComputationMapped = computed<TaxComputationMapped | null>(
    () => mapTaxComputationData(taxComputationData.value),
  )

  /**
   * processedSchedules — the KEY improvement for the template.
   *
   * Previously the template called `handleProfitsTaxComputationDataContent()` TWICE per schedule
   * (once in v-if, once in v-for). That function does non-trivial filtering each time.
   *
   * Now we pre-compute the processed content for every schedule in a single computed property.
   * The template simply iterates over `processedSchedules` — no duplicate work.
   */
  const processedSchedules = computed<ProcessedSchedule[]>(() => {
    const mapped = taxComputationMapped.value
    if (!mapped)
      return []

    return mapped.taxSchedules.map(schedule => ({
      scheduleName: schedule.scheduleName,
      scheduleNumber: schedule.scheduleNumber,
      processedContent: processDataContent(schedule.scheduleName, schedule.dataContentList),
    }))
  })

  /**
   * Flatten the Profits Tax Computation schedule into a pipe-delimited string
   * suitable for clipboard copy.
   *
   * Output format:
   *   taxRate|16.50%;data-content-1-name|Salary;data-content-1-sch|1;data-content-1-amount|50000;checkbox|Some option
   */
  function flattenTaxComputationData(): { taxRate: string; extracted: unknown[]; flattenedString: string } | null {
    const mapped = taxComputationMapped.value
    if (!mapped)
      return null

    // Find the Profits Tax Computation schedule
    const profitsSchedule = mapped.taxSchedules.find(s => isProfitsTaxSchedule(s.scheduleName))
    const dataContentList = profitsSchedule?.dataContentList ?? []

    const extracted: unknown[] = []

    for (const [dataContentIdx, item] of dataContentList.entries()) {
      if (!item || typeof item !== 'object')
        continue

      const dataContentTag = `data-content-${dataContentIdx + 1}`
      const row = item as Record<string, unknown>
      const type = String(row.type ?? '')

      if (type === 'info') {
        const tableData = Array.isArray(row.tableData) ? row.tableData : []
        // Uses the SAME shared filter as the display logic — no more duplication
        const filtered = filterSelectedTableRows(tableData)

        extracted.push(...filtered.map(tr => ({
          dataContentTag,
          name: tr.name ?? '',
          schedule: tr.schedule ?? '',
          amount: tr.this ?? '',
        })))
      }
      else if (type === 'checkboxes') {
        const selectedCheckbox = Array.isArray(row.selectedCheckbox) ? row.selectedCheckbox : []
        extracted.push(...selectedCheckbox.filter(v => typeof v === 'string'))
      }
    }

    // Build the flat string representation
    const flattenedStringParts: string[] = [`taxRate|${mapped.taxRate}`]
    for (const entry of extracted) {
      if (typeof entry === 'string') {
        flattenedStringParts.push(`checkbox|${entry}`)
        continue
      }
      const e = entry as Record<string, unknown>
      const tag = String(e.dataContentTag ?? '')
      flattenedStringParts.push(`${tag}-name|${String(e.name ?? '')}`)
      flattenedStringParts.push(`${tag}-sch|${String(e.schedule ?? '')}`)
      flattenedStringParts.push(`${tag}-amount|${String(e.amount ?? '')}`)
    }

    const flattenedString = flattenedStringParts.join(';')
    return { taxRate: mapped.taxRate, extracted, flattenedString }
  }

  return {
    taxComputationMapped,
    processedSchedules,
    flattenTaxComputationData,
  }
}
