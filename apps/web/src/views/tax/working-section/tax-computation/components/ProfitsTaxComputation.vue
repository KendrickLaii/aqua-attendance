<script setup lang="ts">
export interface TableRow {
  titleSelect?: boolean
  total?: boolean
  itemSelect?: boolean
  name: string
  schedule?: string
  scheduleType?: 'title' | 'currency' | 'label' | 'input' | 'comboBox'
  type?: 'fixedRow' | 'breakdown' | 'total' | 'info' | 'subtotal' | 'blankRow'
  tag?: string[]
  yearSum?: boolean
  this?: string
  last?: string
  number?: number
  noTotalNum?: number
  this_sum_error?: boolean
  last_sum_error?: boolean
  /** subtotal row: start/end are the indices of the range being summed */
  start?: number
  end?: number
}

export interface DataContentItem {
  order: number
  type: string
  tableType?: string
  tableData?: TableRow[]
  content?: string
  checkboxContent?: { title: string; value: string }[]
  selectedCheckbox?: string[]
}

import AmountInput from './AmountInput.vue'
import ConfirmDialog from '@/components/dialogs/tax/ConfirmDialog.vue'
import AppToastStack from '@/components/AppToastStack.vue'
import { useToast } from '@/composables/useToast'
import type { Content } from '@/types/client'
import type { AmountList } from '../TaxComputation.vue'
import type { GroupedDataItem } from './DPL.vue'
import type { BasicInformationData } from '@/types/working-section'
import {
  buildBasicPeriodLine,
  buildBasicPeriodProvisionalLine,
  buildYearsOfAssessmentLine,
  buildYearsOfAssessmentProvisionalLine,
} from '@/helper/taxComputation'

const { show: showToast } = useToast()

const isDebugMode = import.meta.env.VITE_ENV_MODE === 'dev' ? true : false // for debugging

const SCHEDULE_OPTIONS = [
  { title: 'I', value: 'I' },
  { title: 'II', value: 'II' },
  { title: 'III', value: 'III' },
  { title: 'IV', value: 'IV' },
  { title: 'V', value: 'V' },
  { title: 'VI', value: 'VI' },
]

const TAX_REDUCTION_OPTIONS: { title: string; value: number }[] = [
  { title: 'Less: one-off tax reduction (maximum HK$1,500)', value: -1500 },
  { title: 'Less: one-off tax reduction (maximum HK$3,000)', value: -3000 },
  { title: 'Less: one-off tax reduction (maximum HK$6,000)', value: -6000 },
  { title: 'Less: one-off tax reduction (maximum HK$10,000)', value: -10000 },
  { title: 'Less: one-off tax reduction (maximum HK$20,000)', value: -20000 },
]

// Cap the tax reduction by the same table's tax amount and keep the stored value negative.
function getBoundedTaxReductionValue(order: number, selectedValue: number): string {
  const currentItem = props.dataContentList.find(item => item.order === order)
  const taxRateRow = currentItem?.tableData?.find(row => row.tag?.includes('taxRatePercentage'))
  const taxRateValue = parseAmount(taxRateRow?.this ?? '')
  const reductionValue = Math.abs(selectedValue)

  if (taxRateValue <= 0)
    return '-'

  return formatTotalDisplay(Math.min(taxRateValue, reductionValue) * -1)
}

/**
 * Handles value change from the tax reduction combobox (VCombobox).
 * VCombobox emits different types: object when user selects from dropdown,
 * string when user types manually, or null when cleared.
 *
 * @param val - Selected option object { title, value }, or raw string from manual input, or null
 * @param order - Table/section order index
 * @param rowNumber - Row index for this breakdown
 */
function onTaxReductionComboBoxChange(
  val: string | { title: string; value: number } | null,
  order: number,
  rowNumber: number,
) {
  const rv = getRowValue(order, rowNumber)
  if (val == null) {
    rv.label = ''
    rv.thisVal = ''
    return
  }
  if (typeof val === 'string') {
    // VCombobox passes a string on manual typing; keep the typed text as label
    rv.label = val
    const option = TAX_REDUCTION_OPTIONS.find(o => o.title === val)
    rv.thisVal = option != null ? getBoundedTaxReductionValue(order, option.value) : rv.thisVal
    return
  }
  // User selected from dropdown: val is { title, value }
  rv.label = val.title ?? ''
  rv.thisVal = getBoundedTaxReductionValue(order, val.value)
}

const props = defineProps<{
  dataContentList: DataContentItem[]
  clientData?: Content | null
  clientCurrency?: { currency: string; symbol: string; uuid: string } | null
  basicInformationData: BasicInformationData
  taxRate?: number
  groupedData?: GroupedDataItem[]
  scheduleNumber?: string
  amountList: AmountList[]
}>()

const currencyLabel = computed(() => props.clientCurrency?.currency || props.clientData?.currency || 'HKD')

const totalTaxPayableLabels = computed(() => {
  const bi = props.basicInformationData
  const yoaLy = String(bi?.year_of_assessment_ly ?? '').trim() || '–'
  const yoa = String(bi?.year_of_assessment ?? '').trim() || '–'
  const provLy = String(bi?.provisional_ly ?? '').trim() || '–'
  const prov = String(bi?.provisional ?? '').trim() || '–'

  return {
    fixedRowName: `Total tax payable for the year of assessment ${yoaLy}/${yoa}`,
    totalRowName: `\u00A0\u00A0\u00A0and ${provLy}/${prov} (provisional)`,
  }
})

const emit = defineEmits<{
  (e: 'update:tableData', payload: { order: number; tableData: TableRow[] }): void
  (e: 'update:amount-before-tax', value: number): void
  (e: 'update:net-assessable-profit', value: number): void
  (e: 'update:profit-adjustment', value: number): void
  (e: 'update:year-of-assessment', value: number): void
  (e: 'update:year-of-assessment-provisional', value: number): void
  (e: 'update:profit-tax-current-year', value: number): void
  (e: 'update:profit-tax-provisional', value: number): void
  (e: 'update:total-tax-payable', value: number): void
  (e: 'update:text-content', payload: { order: number; content: string }): void
  (e: 'update:selected-checkbox', payload: { order: number; value: string[] }): void
}>()

// Keep `totalTaxPayable` labels in sync with `basicInformationData`.
// Why: these labels are stored in `tableData` (so they can be persisted), but the source of truth
// is Basic Information. This watcher updates ONLY the label rows (fixedRow/total `name`) and never
// touches user-entered amounts.
watch(totalTaxPayableLabels, (labels) => {
  if (!labels?.fixedRowName) return
  const item = props.dataContentList.find(i => i.tableType === 'totalTaxPayable' && Array.isArray(i.tableData))
  if (!item?.tableData?.length) return
  const fixedIdx = item.tableData.findIndex(r => r.type === 'fixedRow' && r.tag?.includes('noInput'))
  const totalIdx = item.tableData.findIndex(r => r.type === 'total')
  if (fixedIdx < 0 && totalIdx < 0) return

  const nextTableData = item.tableData.map((r, i) => {
    if (i === fixedIdx && r.name !== labels.fixedRowName) return { ...r, name: labels.fixedRowName }
    if (i === totalIdx && r.name !== labels.totalRowName) return { ...r, name: labels.totalRowName }
    return r
  })

  // Avoid emitting if nothing changed
  const changed = nextTableData.some((r, i) => r !== item.tableData![i])
  if (!changed) return
  emit('update:tableData', { order: item.order, tableData: nextTableData })
}, { immediate: true })

const yearOfAssessmentLabels = computed(() => {
  const bi = props.basicInformationData
  return {
    line1: buildYearsOfAssessmentLine(bi),
    line2: buildBasicPeriodLine(bi),
  }
})

// Keep `yearOfAssessment` header lines in sync with `basicInformationData`.
// These two lines are stored as `noInput` fixedRows in `tableData` so they can be saved/restored.
watch(yearOfAssessmentLabels, (labels) => {
  const item = props.dataContentList.find(i => i.tableType === 'yearOfAssessment' && Array.isArray(i.tableData))
  if (!item?.tableData?.length) return

  const fixed = item.tableData
    .map((r, idx) => ({ r, idx }))
    .filter(x => x.r.type === 'fixedRow' && x.r.tag?.includes('noInput'))

  if (fixed.length < 2) return
  const [a, b] = fixed

  const next = item.tableData.map((r, i) => {
    if (i === a.idx && r.name !== labels.line1) return { ...r, name: labels.line1 }
    if (i === b.idx && r.name !== labels.line2) return { ...r, name: labels.line2 }
    return r
  })

  const changed = next.some((r, i) => r !== item.tableData![i])
  if (!changed) return
  emit('update:tableData', { order: item.order, tableData: next })
}, { immediate: true })

const yearOfAssessmentProvisionalLabels = computed(() => {
  const bi = props.basicInformationData
  return {
    line1: buildYearsOfAssessmentProvisionalLine(bi),
    line2: buildBasicPeriodProvisionalLine(bi),
  }
})

// Keep `yearOfAssessmentProvisional` header lines in sync with `basicInformationData`.
// Like the current-year card, we persist these as `noInput` fixedRows and only update their `name`.
watch(yearOfAssessmentProvisionalLabels, (labels) => {
  const item = props.dataContentList.find(i => i.tableType === 'yearOfAssessmentProvisional' && Array.isArray(i.tableData))
  if (!item?.tableData?.length) return

  const fixed = item.tableData
    .map((r, idx) => ({ r, idx }))
    .filter(x => x.r.type === 'fixedRow' && x.r.tag?.includes('noInput'))

  if (fixed.length < 2) return
  const [a, b] = fixed

  const next = item.tableData.map((r, i) => {
    if (i === a.idx && r.name !== labels.line1) return { ...r, name: labels.line1 }
    if (i === b.idx && r.name !== labels.line2) return { ...r, name: labels.line2 }
    return r
  })

  const changed = next.some((r, i) => r !== item.tableData![i])
  if (!changed) return
  emit('update:tableData', { order: item.order, tableData: next })
}, { immediate: true })

// rowValues keyed by `${order}-${number}` so multiple tables don't clash
const rowValues = ref<Record<string, { label: string; schedule: string; thisVal: string; lastVal: string }>>({})

function rowKey(order: number, number: number) {
  return `${order}-${number}`
}

function getRowValue(order: number, number: number) {
  const key = rowKey(order, number)
  if (!rowValues.value[key])
    rowValues.value[key] = { label: '', schedule: '', thisVal: '', lastVal: '' }
  return rowValues.value[key]
}

function findAmountListItemByType(type: string) {
  return props.amountList.find(a => a.type === type)
}

// --- Shared: parse amount & format total ---
function parseAmount(s: string | undefined): number {
  if (s == null) return 0
  const t = String(s).trim()
  if (!t || t === '-') return 0

  // Support "(1,234)" negative format and comma-separated numbers.
  const isParenNegative = /^\(.*\)$/.test(t)
  const stripped = t.replace(/[(),\s]/g, '')
  const numeric = isParenNegative ? `-${stripped}` : stripped
  const n = Number(numeric)
  return Number.isNaN(n) ? 0 : n
}

function formatTotalDisplay(n: number): string {
  if (n === 0) return '-'
  const abs = Math.abs(n).toLocaleString('en-US')
  return n < 0 ? `(${abs})` : abs
}

// --- Shared: renumber breakdowns ---
function renumberBreakdowns(data: TableRow[]): TableRow[] {
  // Preserve existing numbering for "fixed" breakdown rows (e.g. one-off reduction, provisional already charged),
  // so syncing/two-tier insertion won't shift rowValues mapping keyed by `row.number`.
  const used = new Set<number>()
  for (const r of data) {
    if (r.type === 'breakdown' && typeof r.number === 'number' && r.number > 0 && !r.tag?.includes(REMAINING_AT_165_TAG))
      used.add(r.number)
  }
  let nextNum = 1
  const alloc = () => {
    while (used.has(nextNum)) nextNum++
    used.add(nextNum)
    return nextNum++
  }

  return data.map((r) => {
    if (r.type !== 'breakdown') return r

    // The two-tier "Remaining @16.5%" row is a computed row; keep its number unset/0.
    if (r.tag?.includes(REMAINING_AT_165_TAG))
      return { ...r, number: r.number ?? 0, noTotalNum: r.noTotalNum ?? 0 }

    // Keep existing positive numbering stable.
    if (typeof r.number === 'number' && r.number > 0)
      return r

    const n = alloc()
    return { ...r, number: n, noTotalNum: n }
  })
}

// --- Per-item helpers ---
function getTitleRow(item: DataContentItem) {
  return (item.tableData ?? []).find(r => r.titleSelect)
}
function getCurrencyRow(item: DataContentItem) {
  return (item.tableData ?? []).find(r => r.scheduleType === 'currency')
}
function getBodyRows(item: DataContentItem) {
  return (item.tableData ?? []).filter(r => !r.titleSelect && r.scheduleType !== 'currency')
}
function getFixedRow(item: DataContentItem) {
  return (item.tableData ?? []).find(r => r.type === 'fixedRow')
}
function getTotalRow(item: DataContentItem) {
  return (item.tableData ?? []).find(r => r.type === 'total' && r.total === true)
}

function computeTotalThisSum(item: DataContentItem): number {
  const bodyRows = getBodyRows(item)
  let sum = 0
  // Sum all fixedRows (e.g. "Profit before tax" and "First HK$2,000,000... @8.25%" when type is fixedRow)
  for (const row of bodyRows) {
    if (row.type === 'fixedRow')
      sum += parseAmount(row.this ?? '')
  }
  // Sum all breakdowns (prefer row.this when present so Sync/tag rows are included)
  const breakdowns = bodyRows.filter((r): r is TableRow & { number: number } => r.type === 'breakdown' && r.number != null)
  for (const row of breakdowns) {
    const fromRow = row.this !== undefined && String(row.this).trim() !== ''
    const amount = fromRow ? row.this : getRowValue(item.order, row.number).thisVal
    sum += parseAmount(amount ?? '')
  }
  return sum
}

function computeTotalThisSumFromData(item: DataContentItem, data: TableRow[]): number {
  const bodyRows = (data ?? []).filter(r => !r.titleSelect && r.scheduleType !== 'currency')
  let sum = 0

  for (const row of bodyRows) {
    if (row.type === 'fixedRow')
      sum += parseAmount(row.this ?? '')
  }

  const breakdowns = bodyRows.filter((r): r is TableRow & { number: number } => r.type === 'breakdown' && r.number != null)
  for (const row of breakdowns) {
    const fromRow = row.this !== undefined && String(row.this).trim() !== ''
    const amount = fromRow ? row.this : getRowValue(item.order, row.number).thisVal
    sum += parseAmount(amount ?? '')
  }

  return sum
}

function refreshComputedRows(item: DataContentItem, data: TableRow[]): TableRow[] {
  const next = refreshSubtotal(data)
  const totalIdx = next.findIndex(r => r.type === 'total' && r.total === true)
  if (totalIdx < 0) return next

  const total = computeTotalThisSumFromData(item, next)
  const totalRow = next[totalIdx]
  const patched = { ...totalRow, this: formatTotalDisplay(total) }
  return next.map((r, i) => (i === totalIdx ? patched : r))
}

/**
 * If the data contains a subtotal row (tag: REMAINING_AT_165_TAG, type: 'subtotal'),
 * recalculate its start/end/this based on the current positions of
 * taxRatePercentage (a) and oneOffTaxReduction (b).
 */
function refreshSubtotal(data: TableRow[]): TableRow[] {
  const subtotalIdx = data.findIndex(r => r.type === 'subtotal')
  if (subtotalIdx < 0) return data

  const a = data.findIndex(r => r.tag?.includes('taxRatePercentage'))
  const b = subtotalIdx - 1 // subtotal is placed right after oneOffTaxReduction
  if (a < 0 || b <= a) return data

  const c = data
    .slice(a, b + 1)
    .reduce((sum, r) => sum + parseAmount(r.this ?? ''), 0)

  return data.map((r, i) =>
    i === subtotalIdx ? { ...r, start: a, end: b, this: formatTotalDisplay(c) } : r,
  )
}

function updateRow(patch: Partial<TableRow>, rowRef: TableRow, item: DataContentItem) {
  const data = item.tableData ?? []
  const patched = data.map(r => r === rowRef ? { ...r, ...patch } : r)
  emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, patched) })
}

function addBreakdownAfter(row: TableRow, item: DataContentItem) {
  const data = item.tableData ?? []
  const idx = data.findIndex(r => r === row)
  if (idx < 0) return
  const newBreakdown: TableRow = {
    itemSelect: true,
    name: '',
    schedule: '',
    scheduleType: 'input',
    type: 'breakdown',
    yearSum: true,
    this: '',
    last: '',
    number: 0,
    noTotalNum: 0,
  }
  const next = [...data]
  const insertAt = row.type === 'subtotal' ? idx + 2 : idx + 1
  next.splice(insertAt, 0, newBreakdown)
  emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, renumberBreakdowns(next)) })
}

const showDeleteConfirm = ref(false)
let rowToDelete: TableRow | null = null
let itemToDelete: DataContentItem | null = null

function requestDeleteBreakdown(row: TableRow, item: DataContentItem) {
  rowToDelete = row
  itemToDelete = item
  showDeleteConfirm.value = true
}

function confirmDeleteBreakdown() {
  if (!rowToDelete || !itemToDelete) return
  const data = itemToDelete.tableData ?? []
  const next = data.filter(r => r !== rowToDelete)
  emit('update:tableData', { order: itemToDelete.order, tableData: refreshComputedRows(itemToDelete, renumberBreakdowns(next)) })
  rowToDelete = null
  itemToDelete = null
}

let isSyncingFromParent = false

// Sync rowValues from tableData when dataContentList has breakdown rows
watch(() => props.dataContentList, (list) => {
  isSyncingFromParent = true
  const next: Record<string, { label: string; schedule: string; thisVal: string; lastVal: string }> = {}
  ;(list ?? []).forEach((item) => {
    const breakdowns = (item.tableData ?? []).filter((r): r is TableRow & { number: number } =>
      r.type === 'breakdown' && r.number != null && !r.tag?.includes(REMAINING_AT_165_TAG),
    )
    for (const row of breakdowns) {
      const key = rowKey(item.order, row.number)
      next[key] = {
        label: row.name ?? '',
        schedule: row.schedule ?? '',
        thisVal: row.this ?? '',
        lastVal: row.last ?? '',
      }
    }
  })
  rowValues.value = next
  nextTick(() => { isSyncingFromParent = false })
}, { immediate: true, deep: true })

// When rowValues change (user edit), push back to each item's tableData and emit
function syncBreakdownToTableData() {
  if (isSyncingFromParent) return
  ;(props.dataContentList ?? []).forEach((item) => {
    const data = item.tableData ?? []
    if (data.length === 0) return
    const patched = data.map((r) => {
      if (r.type !== 'breakdown' || r.number == null) return r
      if (r.tag?.includes(REMAINING_AT_165_TAG)) return r
      const v = rowValues.value[rowKey(item.order, r.number)]
      if (!v) return r
      return { ...r, name: v.label, schedule: v.schedule, this: v.thisVal, last: v.lastVal }
    })
    emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, patched) })
  })
}

watch(rowValues, () => syncBreakdownToTableData(), { deep: true })

// --- Sync (profitAdjustment: from DPL groupedData) ---
function insertAddBackItem(item: DataContentItem, baseData?: TableRow[]) {
  const source = baseData ?? (item.tableData ?? [])
  const withoutBreakdown = source.filter(r => r.type !== 'breakdown')
  const amountBeforeTaxIdx = withoutBreakdown.findIndex(r => r.type === 'fixedRow' && r.tag?.includes('amountBeforeTax'))
  const insertIndex = amountBeforeTaxIdx >= 0 ? amountBeforeTaxIdx + 1 : withoutBreakdown.length

  const groupedData = props.groupedData ?? []
  const addBackItems = groupedData.filter(i => i.addBack === true)
  const sortedAddBackItems = [
    ...addBackItems.filter(i => i.current_year >= 0),
    ...addBackItems.filter(i => i.current_year < 0),
  ]

  const newRows: TableRow[] = sortedAddBackItems.map((groupItem, index) => {
    const prefix = groupItem.current_year >= 0 ? 'Add' : 'Less'
    const num = index + 1
    return {
      itemSelect: true,
      name: `${prefix}: ${groupItem.content}`,
      schedule: groupItem.scheduleNumber,
      scheduleType: 'input' as const,
      type: 'breakdown' as const,
      yearSum: true,
      this: formatTotalDisplay(groupItem.current_year),
      last: '',
      number: num,
      noTotalNum: num,
    }
  })

  const next = [...withoutBreakdown]
  next.splice(insertIndex, 0, ...newRows)
  emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, next) })
}

const REMAINING_AT_165_TAG = 'remainingAt165'

/**
 * Two-tier helper: given the current data array (with taxRatePercentage already patched),
 * inserts only the "Remaining @16.5%" breakdown row right after taxRatePercentage.
 * The subtotal row is assumed to already exist in the initial data and is maintained
 * by refreshSubtotal() after each update.
 */
function buildTwoTierRows(data: TableRow[], currentYear: number): TableRow[] {
  const remaining = currentYear - 2000000
  const remainingTax = Math.trunc(remaining * 0.165)

  const newRow: TableRow = {
    itemSelect: true,
    name: `Remaining HK$${remaining.toLocaleString()} of assessable profit @16.5%`,
    schedule: '',
    scheduleType: 'input',
    type: 'fixedRow',
    tag: [REMAINING_AT_165_TAG],
    yearSum: true,
    this: formatTotalDisplay(remainingTax),
    last: '',
  }

  // Insert immediately after taxRatePercentage
  const taxRateIdx = data.findIndex(r => r.tag?.includes('taxRatePercentage'))
  const insertAt = taxRateIdx >= 0 ? taxRateIdx + 1 : data.length
  return [...data.slice(0, insertAt), newRow, ...data.slice(insertAt)]
}

/**
 * Sync: pull values from amountList/groupedData into this table depending on tableType.
 * - profitAdjustment: from DPL "before tax" → fixedRow, then rebuild breakdowns from add-back items; emit amount-before-tax.
 * - yearOfAssessment: amountList.profit_adjustment.current_year → fixedRow.this.
 * - profitTaxCurrentYear: amountList.year_of_assessment.current_year + taxRate → taxRatePercentage row (name + this); if two-tier (8.25% & >2M), add "Remaining @16.5%" row.
 * - profitTaxProvisional: amountList.year_of_assessment_provisional.current_year + taxRate → taxRatePercentage row (name + this); if two-tier (8.25% & >2M), add "Remaining @16.5%" row.
 */
function onSync(item: DataContentItem) {
  // --- profitAdjustment: sync "Profit before tax" from DPL and rebuild breakdown rows from add-back items ---
  if (item.tableType === 'profitAdjustment') {
    const list = props.groupedData ?? []
    const match = list.find(i => typeof i.content === 'string' && i.content.endsWith(' before tax'))
    const row = getFixedRow(item)
    if (!match || !row) return
    const patch = { name: match.content, schedule: match.scheduleNumber, ['this']: formatTotalDisplay((match.current_year) * -1) } as Partial<TableRow>
    const data = item.tableData ?? []
    const nextAfterFixed = data.map(r => r === row ? { ...r, ...patch } : r)
    insertAddBackItem(item, nextAfterFixed)
    emit('update:amount-before-tax', match.current_year)
    showToast('Synced successfully.', 'info')
    return
  }

  // --- yearOfAssessment: copy profit_adjustment.current_year into fixedRow.this ---
  if (item.tableType === 'yearOfAssessment') {
    const amountListItem = findAmountListItemByType('profit_adjustment')
    const row = (item.tableData ?? []).find(r => r.type === 'fixedRow' && r.tag?.includes('syncTarget'))
    if (amountListItem == null || !row) return
    const patch = { ['this']: formatTotalDisplay(amountListItem.current_year) } as Partial<TableRow>
    const data = item.tableData ?? []
    const next = data.map(r => r === row ? { ...r, ...patch } : r)
    emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, next) })
    showToast('Synced successfully.', 'info')
    return
  }

  // --- yearOfAssessmentProvisional: copy year_of_assessment.current_year into total row's this ---
  if (item.tableType === 'yearOfAssessmentProvisional') {
    const amountListItem = findAmountListItemByType('year_of_assessment')
    const totalRow = getTotalRow(item)
    if (amountListItem == null || !totalRow) return
    const patch = { this: formatTotalDisplay(amountListItem.current_year) } as Partial<TableRow>
    const data = item.tableData ?? []
    const next = data.map(r => r === totalRow ? { ...r, ...patch } : r)
    emit('update:tableData', { order: item.order, tableData: next })
    showToast('Synced successfully.', 'info')
    return
  }
  
  if (item.tableType === 'netAssessableProfit') {
    const amountListItem = findAmountListItemByType('year_of_assessment')
    const row = (item.tableData ?? []).find(r => r.type === 'fixedRow' && r.tag?.includes('syncTarget'))
    if (amountListItem == null || !row) return
    const patch = { ['this']: formatTotalDisplay(amountListItem.current_year) } as Partial<TableRow>
    const data = item.tableData ?? []
    const next = data.map(r => r === row ? { ...r, ...patch } : r)
    emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, next) })
    showToast('Synced successfully.', 'info')
    return
  }

  // --- profitTaxCurrentYear: set taxRatePercentage row from net_assessable_profit.current_year and taxRate; two-tier adds "Remaining @16.5%" row ---
  if (item.tableType === 'profitTaxCurrentYear') {
    const amountListItem = findAmountListItemByType('net_assessable_profit')
    const taxRateRow = (item.tableData ?? []).find(r => r.tag?.includes('taxRatePercentage'))
    if (amountListItem == null || !taxRateRow) return
    const taxRate = props.taxRate ?? 0.165
    const currentYear = amountListItem.current_year
    const isTwoTier = taxRate === 0.0825 && currentYear > 2000000
    // Label: two-tier shows first 2M @8.25%; else single rate label
    const name = isTwoTier
      ? 'First HK$2,000,000 of assessable profit @8.25%'
      : (taxRate === 0.0825 ? 'Profits tax thereon @8.25%' : 'Profits tax thereon @16.5%')
    // Amount: negative current year yields 0; two-tier uses fixed 165000; otherwise trunc(currentYear * taxRate)
    let taxAmount = 0
    if (currentYear < 0)
      taxAmount = 0
    else if (isTwoTier)
      taxAmount = 165000
    else
      taxAmount = Math.trunc(currentYear * taxRate)
    const patch = { this: formatTotalDisplay(taxAmount), name } as Partial<TableRow>
    let data = (item.tableData ?? []).map(r => r === taxRateRow ? { ...r, ...patch } : r)

    // Remove all REMAINING_AT_165_TAG rows; re-add the breakdown row only when two-tier
    data = data.filter(r => !r.tag?.includes(REMAINING_AT_165_TAG))
    if (isTwoTier)
      data = buildTwoTierRows(data, currentYear)

    emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, renumberBreakdowns(data)) })
    showToast('Synced successfully.', 'info')
    return
  }

  // --- profitTaxProvisional: set taxRatePercentage row from year_of_assessment_provisional.current_year and taxRate; two-tier adds "Remaining @16.5%" row ---
  if (item.tableType === 'profitTaxProvisional') {
    const amountListItem = findAmountListItemByType('year_of_assessment_provisional')
    const taxRateRow = (item.tableData ?? []).find(r => r.tag?.includes('taxRatePercentage'))
    if (amountListItem == null || !taxRateRow) return
    const taxRate = props.taxRate ?? 0.165
    const currentYear = amountListItem.current_year
    const isTwoTier = taxRate === 0.0825 && currentYear > 2000000
    const name = isTwoTier
      ? 'First HK$2,000,000 of assessable profit @8.25%'
      : (taxRate === 0.0825 ? 'Profits tax thereon @8.25%' : 'Profits tax thereon @16.5%')

    let taxAmount = 0
    if (currentYear < 0)
      taxAmount = 0
    else if (isTwoTier)
      taxAmount = 165000
    else
      taxAmount = Math.trunc(currentYear * taxRate)

    const patch = { this: formatTotalDisplay(taxAmount), name } as Partial<TableRow>
    let data = (item.tableData ?? []).map(r => r === taxRateRow ? { ...r, ...patch } : r)

    // Remove all REMAINING_AT_165_TAG rows; re-add the breakdown row only when two-tier
    data = data.filter(r => !r.tag?.includes(REMAINING_AT_165_TAG))
    if (isTwoTier)
      data = buildTwoTierRows(data, currentYear)

    emit('update:tableData', { order: item.order, tableData: refreshComputedRows(item, renumberBreakdowns(data)) })
    showToast('Synced successfully.', 'info')
    return
  }
}

// --- Post: write total to amountList (by tableType; parent can route) ---
function onPost(item: DataContentItem) {
  const value = computeTotalThisSum(item)
  if (item.tableType === 'profitAdjustment')
    emit('update:profit-adjustment', value)
  if (item.tableType === 'yearOfAssessment')
    emit('update:year-of-assessment', value)
  if (item.tableType === 'netAssessableProfit')
    emit('update:net-assessable-profit', value)
  if (item.tableType === 'yearOfAssessmentProvisional') {
    const totalRow = getTotalRow(item)
    const raw = totalRow?.this ?? ''
    emit('update:year-of-assessment-provisional', parseAmount(raw))
  }
  if (item.tableType === 'profitTaxCurrentYear')
    emit('update:profit-tax-current-year', value)
  if (item.tableType === 'profitTaxProvisional') {
    const balanceBoughtForward = findAmountListItemByType('profit_tax_current_year')?.current_year ?? 0
    const totalTaxPayableValue = balanceBoughtForward + value
    const totalTaxPayableItem = props.dataContentList.find(i => i.tableType === 'totalTaxPayable')
    const totalTaxPayableRow = totalTaxPayableItem ? getTotalRow(totalTaxPayableItem) : undefined

    if (totalTaxPayableItem && totalTaxPayableRow) {
      const next = (totalTaxPayableItem.tableData ?? []).map(r =>
        r === totalTaxPayableRow ? { ...r, this: formatTotalDisplay(totalTaxPayableValue) } : r,
      )
      emit('update:tableData', { order: totalTaxPayableItem.order, tableData: next })
    }

    emit('update:profit-tax-provisional', value)
    emit('update:total-tax-payable', totalTaxPayableValue)
  }
    showToast('Posted successfully.', 'info')
}
</script>

<template>
  <template v-for="item in dataContentList" :key="item.order">
    <!-- profitAdjustment / profitTaxCurrentYear / profitTaxProvisional: card + table with Sync, breakdown (+/-), Post -->
    <VCard v-if="['profitAdjustment', 'profitTaxCurrentYear', 'profitTaxProvisional', 'netAssessableProfit'].includes(item.tableType ?? '')" class="ptc-card pa-4 ma-3">
      <div class="ptc-table">
        <div v-if="getTitleRow(item)" class="ptc-row ptc-header">
          {{ isDebugMode ? `(Dev)tableType: ${item.tableType}` : '' }}
          <VBtn v-if="isDebugMode" color="primary" size="x-small" @click="console.log('tableData', item.tableData)">(Dev)tableData</VBtn>
          <div class="ptc-cell ptc-name" />
          <div class="ptc-cell ptc-schedule text-center text-decoration-underline">{{ getTitleRow(item)!.schedule || "Schedule" }}</div>
          <div class="ptc-cell ptc-amount text-center text-decoration-underline">{{ getTitleRow(item)!.this || "Amount" }}</div>
          <div class="ptc-cell ptc-action">
            <VBtn color="primary" size="x-small" @click="onSync(item)">Sync</VBtn>
          </div>
        </div>
        <div v-if="getCurrencyRow(item)" class="ptc-row ptc-currency">
          <div class="ptc-cell ptc-name" />
          <div class="ptc-cell ptc-schedule" />
          <div class="ptc-cell ptc-amount text-center">{{ getCurrencyRow(item)!.this || currencyLabel }}</div>
          <div class="ptc-cell ptc-action" />
        </div>
        <template v-for="(row, rowIdx) in getBodyRows(item)" :key="`${row.type}-${row.number ?? rowIdx}`">
          <div v-if="row.type === 'blankRow'" class="ptc-row ptc-blank-row">
            <div class="ptc-cell ptc-name" />
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount" />
            <div class="ptc-cell ptc-action" />
          </div>
          <div v-else-if="row.type === 'fixedRow'" class="ptc-row">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule">
              <VSelect
                v-if="!row.tag?.includes('noInput')"
                :model-value="row.schedule"
                :items="SCHEDULE_OPTIONS"
                density="compact"
                hide-details
                variant="outlined"
                class="ptc-schedule-input"
                @update:model-value="updateRow({ schedule: $event }, row, item)"
              />
            </div>
            <div class="ptc-cell ptc-amount">
              <AmountInput
                v-if="!row.tag?.includes('noInput')"
                :model-value="row.this"
                class="ptc-amount-input"
                @update:model-value="updateRow({ this: $event }, row, item)"
                :disabled="row.tag?.includes('taxRatePercentage') || row.tag?.includes('inputDisabled')"
              />
            </div>
            <div class="ptc-cell ptc-action" />
          </div>
          <div v-else-if="row.type === 'breakdown' || row.type === 'subtotal'" class="ptc-row">
            <div class="ptc-cell ptc-name ptc-breakdown-name">
              <span class="ptc-row-label">{{ row.type === 'subtotal' || row.tag?.includes(REMAINING_AT_165_TAG) ? '' : `(${row.number})` }}</span>
              <span v-if="row.tag?.includes(REMAINING_AT_165_TAG)">{{ row.name }}</span>
              <VCombobox v-if="row.scheduleType === 'comboBox'"
                :model-value="getRowValue(item.order, row.number!).label || row.name"
                :items="TAX_REDUCTION_OPTIONS"
                item-title="title"
                item-value="title"
                density="compact"
                hide-details variant="outlined"
                class="ptc-breakdown-input"
                @update:model-value="(val) => onTaxReductionComboBoxChange(val, item.order, row.number!)"
              />
              <VTextField v-else-if="row.type !== 'subtotal' && !row.tag?.includes(REMAINING_AT_165_TAG)"
                v-model="getRowValue(item.order, row.number!).label"
                density="compact"
                hide-details
                variant="outlined"
                class="ptc-breakdown-input"
              />
            </div>
            <div class="ptc-cell ptc-schedule">
              <VSelect v-if="row.type !== 'subtotal'"
                v-model="getRowValue(item.order, row.number!).schedule"
                :items="SCHEDULE_OPTIONS"
                density="compact"
                hide-details
                variant="outlined"
                class="ptc-schedule-input"
              />
            </div>
            <div class="ptc-cell ptc-amount" :class="{ 'ptc-amount-subtotal': row.type === 'subtotal' }">
              <AmountInput
                v-if="row.type !== 'subtotal' && !row.tag?.includes(REMAINING_AT_165_TAG)"
                v-model="getRowValue(item.order, row.number!).thisVal"
                class="ptc-amount-input"
              />
              <AmountInput
                v-else-if="row.tag?.includes(REMAINING_AT_165_TAG)"
                :model-value="row.this ?? ''"
                class="ptc-amount-input"
                disabled
              />
              <AmountInput
                v-else
                :model-value="row.this ?? ''"
                class="ptc-amount-input"
                disabled
              />
            </div>
            <div class="ptc-cell ptc-action">
              <IconBtn size="x-small" variant="text" color="primary" @click="addBreakdownAfter(row, item)">
                <VIcon icon="ri-add-line" />
              </IconBtn>
              <IconBtn
                :disabled="row.type === 'subtotal' || row.tag?.includes('isBinDisabled') || row.tag?.includes(REMAINING_AT_165_TAG)"
                size="x-small"
                variant="text"
                color="error"
                @click="requestDeleteBreakdown(row, item)"
              >
                <VIcon icon="ri-delete-bin-line" />
              </IconBtn>
            </div>
          </div>
          <div v-else-if="row.type === 'total'" class="ptc-row ptc-total">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount">
              <VTextField
                :model-value="row.this?.trim() ? row.this : '-'"
                density="compact"
                hide-details
                readonly
                class="ptc-total-value"
              />
            </div>
            <div class="ptc-cell ptc-action">
              <VBtn color="primary" size="x-small" @click="onPost(item)">Post</VBtn>
            </div>
          </div>
        </template>
      </div>
    </VCard>

    <!-- yearOfAssessment: card with title + subtitle + table -->
    <VCard v-else-if="item.tableType === 'yearOfAssessment'" class="ptc-card pa-4 ma-3">
      <div class="ptc-table">
        {{ isDebugMode ? `(Dev)tableType: ${item.tableType}` : '' }}
        <VBtn v-if="isDebugMode" color="primary" size="x-small" @click="console.log('tableData', item.tableData)">(Dev)tableData</VBtn>
        <div v-if="getTitleRow(item)" class="ptc-row ptc-header">
          <div class="ptc-cell ptc-name">
            <!-- kept in tableData as noInput fixedRows -->
          </div>
          <div class="ptc-cell ptc-schedule text-center text-decoration-underline">Schedule</div>
          <div class="ptc-cell ptc-amount text-center text-decoration-underline">Amount</div>
          <div class="ptc-cell ptc-action">
            <VBtn color="primary" size="x-small" @click="onSync(item)">Sync</VBtn>
          </div>
        </div>
        <div class="ptc-row ptc-currency">
          <div class="ptc-cell ptc-name" />
          <div class="ptc-cell ptc-schedule" />
          <div class="ptc-cell ptc-amount text-center">{{ currencyLabel }}</div>
          <div class="ptc-cell ptc-action" />
        </div>
        <template v-for="(row, rowIdx) in getBodyRows(item)" :key="`${row.type}-${row.number ?? rowIdx}`">
          <div v-if="row.type === 'fixedRow'" class="ptc-row">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule">
              <VSelect
                v-if="!row.tag?.includes('noInput')"
                :model-value="row.schedule"
                :items="SCHEDULE_OPTIONS"
                density="compact"
                hide-details
                variant="outlined"
                class="ptc-schedule-input"
                @update:model-value="updateRow({ schedule: $event }, row, item)"
              />
            </div>
            <div class="ptc-cell ptc-amount">
              <AmountInput
                v-if="!row.tag?.includes('noInput')"
                :model-value="row.this"
                class="ptc-amount-input"
                @update:model-value="updateRow({ this: $event }, row, item)"
              />
            </div>
            <div class="ptc-cell ptc-action" />
          </div>
          <div v-else-if="row.type === 'breakdown'" class="ptc-row">
            <div class="ptc-cell ptc-name ptc-breakdown-name">
              <span class="ptc-row-label">({{ row.number }})</span>
              <VTextField
                v-model="getRowValue(item.order, row.number!).label"
                density="compact"
                hide-details
                variant="outlined"
                class="ptc-breakdown-input"
              />
            </div>
            <div class="ptc-cell ptc-schedule">
              <VSelect
                v-model="getRowValue(item.order, row.number!).schedule"
                :items="SCHEDULE_OPTIONS"
                density="compact"
                hide-details
                variant="outlined"
                class="ptc-schedule-input"
              />
            </div>
            <div class="ptc-cell ptc-amount">
              <AmountInput
                v-model="getRowValue(item.order, row.number!).thisVal"
                class="ptc-amount-input"
              />
            </div>
            <div class="ptc-cell ptc-action">
              <IconBtn size="x-small" variant="text" color="primary" @click="addBreakdownAfter(row, item)">
                <VIcon icon="ri-add-line" />
              </IconBtn>
              <IconBtn :disabled="row.scheduleType === 'comboBox'" size="x-small" variant="text" color="error" @click="requestDeleteBreakdown(row, item)">
                <VIcon icon="ri-delete-bin-line" />
              </IconBtn>
            </div>
          </div>
          <div v-else-if="row.type === 'total'" class="ptc-row ptc-total">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount">
              <VTextField
                :model-value="row.this?.trim() ? row.this : '-'"
                density="compact"
                hide-details
                readonly
                class="ptc-total-value"
              />
            </div>
            <div class="ptc-cell ptc-action">
              <VBtn color="primary" size="x-small" @click="onPost(item)">Post</VBtn>
            </div>
          </div>
        </template>
      </div>
    </VCard>

    <!-- yearOfAssessmentProvisional: YEARS OF ASSESSMENT (PROVISIONAL) + Basic period + single total row with Post -->
    <VCard v-else-if="item.tableType === 'yearOfAssessmentProvisional'" class="ptc-card pa-4 ma-3">
      <div class="ptc-table">
        {{ isDebugMode ? `(Dev)tableType: ${item.tableType}` : '' }}
        <VBtn v-if="isDebugMode" color="primary" size="x-small" @click="console.log('tableData', item.tableData)">(Dev)tableData</VBtn>
        <div v-if="getTitleRow(item)" class="ptc-row ptc-header">
          <div class="ptc-cell ptc-name">
            <!-- kept in tableData as noInput fixedRows -->
          </div>
          <div class="ptc-cell ptc-schedule text-center text-decoration-underline">Schedule</div>
          <div class="ptc-cell ptc-amount text-center text-decoration-underline">Amount</div>
          <div class="ptc-cell ptc-action">
            <VBtn color="primary" size="x-small" @click="onSync(item)">Sync</VBtn>
          </div>
        </div>
        <div v-if="getCurrencyRow(item)" class="ptc-row ptc-currency">
          <div class="ptc-cell ptc-name"/>
          <div class="ptc-cell ptc-schedule" />
          <div class="ptc-cell ptc-amount text-center">{{ currencyLabel }}</div>
          <div class="ptc-cell ptc-action" />
        </div>
        <template v-for="(row, rowIdx) in getBodyRows(item)" :key="`${row.type}-${row.number ?? rowIdx}`">
          <div v-if="row.type === 'fixedRow'" class="ptc-row">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount" />
            <div class="ptc-cell ptc-action" />
          </div>
          <div v-if="row.type === 'total'" class="ptc-row ptc-total">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount">
              <VTextField
                :model-value="row.this?.trim() ? row.this : '-'"
                density="compact"
                hide-details
                readonly
                class="ptc-total-value"
              />
            </div>
            <div class="ptc-cell ptc-action">
              <VBtn color="primary" size="x-small" @click="onPost(item)">Post</VBtn>
            </div>
          </div>
        </template>
      </div>
    </VCard>

    <!-- totalTaxPayable: summary card, Schedule + Amount, no Sync/Post/+/- -->
    <VCard v-else-if="item.tableType === 'totalTaxPayable'" class="ptc-card pa-4 ma-3">
      <div class="ptc-table">
        {{ isDebugMode ? `(Dev)tableType: ${item.tableType}` : '' }}
        <VBtn v-if="isDebugMode" color="primary" size="x-small" @click="console.log('tableData', item.tableData)">(Dev)tableData</VBtn>
        <div v-if="getTitleRow(item)" class="ptc-row ptc-header">
          <div class="ptc-cell ptc-name" />
          <div class="ptc-cell ptc-schedule text-center text-decoration-underline">Schedule</div>
          <div class="ptc-cell ptc-amount text-center text-decoration-underline">Amount</div>
          <div class="ptc-cell ptc-action" />
        </div>
        <div v-if="getCurrencyRow(item)" class="ptc-row ptc-currency">
          <div class="ptc-cell ptc-name" />
          <div class="ptc-cell ptc-schedule" />
          <div class="ptc-cell ptc-amount text-center">{{ currencyLabel }}</div>
          <div class="ptc-cell ptc-action" />
        </div>
        <template v-for="(row, rowIdx) in getBodyRows(item)" :key="`${row.type}-${row.number ?? rowIdx}`">
          <div v-if="row.type === 'fixedRow'" class="ptc-row">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount" />
            <div class="ptc-cell ptc-action" />
          </div>
          <div v-else-if="row.type === 'total'" class="ptc-row ptc-total">
            <div class="ptc-cell ptc-name">{{ row.name }}</div>
            <div class="ptc-cell ptc-schedule" />
            <div class="ptc-cell ptc-amount">
              <VTextField
                :model-value="row.this ?? '-'"
                density="compact"
                hide-details
                readonly
                class="ptc-total-value"
              />
            </div>
            <div class="ptc-cell ptc-action" />
          </div>
        </template>
      </div>
    </VCard>

    <!-- type="text": show VTextarea for content -->
    <VCard v-else-if="item.type === 'text'" class="ptc-card pa-4 ma-3">
      <VTextarea
        :model-value="item.content ?? ''"
        variant="outlined"
        hide-details
        no-resize
        rows="4"
        class="ptc-textarea"
        @update:model-value="(val) => emit('update:text-content', { order: item.order, content: val ?? '' })"
      />
    </VCard>

    <!-- type="checkboxes": show checkboxes for content -->
    <VCard v-else-if="item.type === 'checkboxes'" class="ptc-card pa-3 ma-3">
      <VCheckbox
        v-for="checkbox in item.checkboxContent"
        :key="checkbox.value"
        class="ptc-checkbox"
        :model-value="item.selectedCheckbox ?? []"
        :value="checkbox.value"
        :label="checkbox.title"
        @update:model-value="(val) => emit('update:selected-checkbox', { order: item.order, value: val ?? [] })"
      />
    </VCard>
  </template>

  <ConfirmDialog
    v-model="showDeleteConfirm"
    header="Confirm Delete"
    text="Are you sure you want to delete this breakdown item? The number will be automatically updated after deletion."
    confirm-button-text="Delete"
    confirm-button-color="error"
    @confirm="confirmDeleteBreakdown"
  />

  <AppToastStack />
</template>

<style lang="scss" scoped>
.ptc-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.2) !important;
}

.ptc-checkbox{
  :deep(.v-label) {
    font-size: 0.75rem;
    text-align: justify;
  }
  
}

.ptc-table {
  width: 100%;
  font-size: 0.75rem;

  :deep(.v-field) {
    --v-field-input-padding-top: 2px;
    --v-field-input-padding-bottom: 2px;
    --v-field-padding-start: 8px;
    --v-field-padding-end: 8px;
    font-size: 0.75rem;
    min-height: 28px !important;
  }

  :deep(.v-field__input) {
    min-height: 28px !important;
    padding-block: 2px !important;
    font-size: 0.75rem;
  }

  :deep(.v-field__append-inner) {
    padding-top: 2px;
  }
}

.ptc-row {
  display: flex;
  align-items: center;
  padding-block: 6px;
  gap: 8px;
}

.ptc-blank-row {
  height: 24px;
}

.ptc-header {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.ptc-currency {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding-block: 2px;
}

.ptc-total {
  font-weight: 600;
}

.ptc-name       { flex: 1 1 auto; min-width: 0; }
.ptc-schedule   { flex: 0 0 70px; }
.ptc-amount     { flex: 0 0 110px; }
.ptc-action     { flex: 0 0 70px; display: flex; justify-content: center; align-items: center; }

.ptc-amount-subtotal{
  position: relative;
}
.ptc-amount-subtotal::before{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: -30px; /* visually move border up without layout padding/margin */ //need add blank row on top manually in taxComputation.ts
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.2);
  
  pointer-events: none;
}
.ptc-breakdown-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ptc-row-label {
  white-space: nowrap;
  flex-shrink: 0;
  font-size: 0.75rem;
  width: 25px;
}

.ptc-schedule-input :deep(.v-field__input) {
  text-align: center;
}

.ptc-amount-input :deep(.v-field__input) {
  text-align: right;
}

.ptc-total-value {
  min-width: 80px;

  :deep(.v-field) {
    background-color: rgb(var(--v-theme-primary)) !important;
  }

  :deep(.v-field__input) {
    color: rgb(var(--v-theme-on-primary)) !important;
    -webkit-text-fill-color: rgb(var(--v-theme-on-primary)) !important;
    text-align: right;
  }
}
.ptc-textarea {
  :deep(.v-field__input) {
    font-size: 0.75rem;
  }
}
</style>
