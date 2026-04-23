<script setup lang="ts">
import ConfirmDialog from '@/components/dialogs/tax/ConfirmDialog.vue'
import type { Content } from '@/types/client'
import type { BasicInformationData } from '@/types/working-section'
import { useToast } from '@/composables/useToast'
import { getNoteACFromAqua } from '@/api/tax-computation'

const { show: showToast } = useToast()

const SCH_OPTIONS = [
  { title: '', value: '' },
  { title: 'I', value: 'I' },
  { title: 'II', value: 'II' },
  { title: 'III', value: 'III' },
  { title: 'IV', value: 'IV' },
  { title: 'V', value: 'V' },
  { title: 'VI', value: 'VI' },
]

const showImportDPLDialog = ref(false)
const importDPLData = ref('')
const onClearImportedData = () => {
  pastedImportGroupedData.value = null
  showToast('Imported data cleared.', 'success')
}

const openImportDPLDialog = () => {
  importDPLData.value = ''
  showImportDPLDialog.value = true
}
const importDataFromAqua = async () => {
  const basicInfo = props.basicInformationData
  if (!basicInfo) {
    showToast('Basic information is missing.', 'error')
    return
  }

  const companyName = basicInfo.companyNameEn || ''
  const yearOfAssessment = basicInfo.year_of_assessment || ''
  const yearOfAssessmentLy = basicInfo.year_of_assessment_ly || ''
  if (!companyName || !yearOfAssessment || !yearOfAssessmentLy) {
    showToast('Missing required fields for Aqua request.', 'error')
    return
  }

  try {
    const res = await getNoteACFromAqua({
      company_name: companyName,
      year_of_assessment: yearOfAssessment, // change value to yearOfAssessment when api ready
      year_of_assessment_ly: yearOfAssessmentLy, // change value to yearOfAssessmentLy when api ready
    })

    console.log('getNoteACFromAqua', res)
    if (!res.DPL) {
      showToast('No DPL data found.', 'error')
      return
    }
    const dpl = res.DPL
    console.log('dpl in Json', JSON.parse(dpl))
    const { items, profitBeforeTaxCurrentYear } = parseImportedDplJsonToGroupedItems(dpl) // items = Display name and sub account, profitBeforeTaxCurrentYear = Profit before tax
    console.log('grouped items', items)
    pastedImportGroupedData.value = items
    applyProfitBeforeTaxCurrentYear(profitBeforeTaxCurrentYear)
    emit('update:localDPL', dpl)
    showToast('Get data successfully.', 'success')
  }
  catch (error) {
    console.error('getNoteACFromAqua failed', error)
    showToast('Failed to fetch note data from Aqua.', 'error')
  }
}
/** each row has 6 columns: [item name, Note, this, last, tag, attr], display Content/Sch./Taxable/This, hide last/tag/attr */
export type DPLRow = [string, string, string, string, string, object]

/** currently focused amount cell */
const focusedAmountKey = ref<string | null>(null)
/** raw input string while editing (e.g. "-" so user can type negative); 0  display as empty so user can type "-" first */
const focusedAmountRaw = ref<string>('')

/** thousands format: negative numbers are wrapped in parentheses */
function formatAmountDisplay(raw: string): string {
  const s = String(raw).replace(/,/g, '').trim()
  if (s === '' || s === '-') return s
  const num = Number.parseFloat(s)
  if (Number.isNaN(num)) return raw
  if (num === 0) return '-'
  const absStr = Math.abs(num).toLocaleString('en-HK')
  return num < 0 ? `(${absStr})` : absStr
}

/** convert displayed value to a string that can be stored (remove commas, convert parentheses to negative numbers) */
function parseAmountInput(display: string): string {
  let s = String(display).replace(/,/g, '').trim()
  const wrapped = /^\((.*)\)$/.exec(s)
  if (wrapped) {
    const inner = wrapped[1].replace(/,/g, '').trim()
    const n = Number.parseFloat(inner)
    return Number.isNaN(n) ? s : String(-n)
  }
  return s
}

/** allow only integers and negative sign: 0123456789-， negative sign can only appear at the beginning */
function sanitizeAmountInput(value: string): string {
  let s = String(value).replace(/[^\d-]/g, '')
  if (s.includes('-') && s[0] !== '-')
    s = s.replace(/-/g, '')
  return s
}

/** keydown: allow only numbers, negative sign and common editing keys, prohibit illegal characters from the start of input */
function onAmountKeydown(e: KeyboardEvent) {
  const key = e.key
  const allowedKeys = ['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight', 'Home', 'End']
  if (allowedKeys.includes(key)) return
  if ((e.ctrlKey || e.metaKey) && key === 'v') return // allow paste, then sanitize
  if ((e.ctrlKey || e.metaKey) && (key === 'a' || key === 'c' || key === 'x')) return
  if (/^\d$/.test(key)) return
  if (key === '-') {
    const target = e.target as HTMLInputElement
    const val = target?.value ?? ''
    const start = target?.selectionStart ?? 0
    if (val === '' || (start === 0 && val[0] !== '-')) return
  }
  e.preventDefault()
}

/** groupedData single item format, table uses this structure for rendering */
export interface GroupedDataItem {
  content: string
  scheduleNumber: string
  addBack: boolean
  current_year: number
  prior_year: number
  tag: string | Record<string, unknown>
  attr: Record<string, any>
}

export interface DPLGroupedData {
  importedData: GroupedDataItem[]
  mannualInputData: GroupedDataItem[]
}

function isPlainObject(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val)
}

/** Column 5 may be a JSON object (after parse) or a JSON string from API. */
function dplJsonCellToAttrObject(cell: unknown): Record<string, unknown> | null {
  if (isPlainObject(cell))
    return cell
  if (typeof cell === 'string' && cell.trim() !== '') {
    try {
      const p = JSON.parse(cell) as unknown
      return isPlainObject(p) ? p : null
    }
    catch {
      return null
    }
  }
  return null
}

/** Parse amount cells: commas, parentheses for negatives, "-" / empty → 0. */
function dplImportAmountToNumber(raw: unknown): number {
  const s = String(raw ?? '').trim()
  if (s === '' || s === '-')
    return 0
  const normalized = parseAmountInput(s)
  const n = Number.parseFloat(normalized)
  return Number.isNaN(n) ? 0 : n
}

/** convert API DPLRow to GroupedDataItem, used for table and groupedData */
function dplRowToGroupedItem(row: DPLRow): GroupedDataItem {
  const r = row as unknown as unknown[]
  const thisVal = Number.parseFloat(parseAmountInput(String(r[2] ?? '')))
  const priorVal = Number.parseFloat(parseAmountInput(String(r[3] ?? '')))
  const tagStr = String(r[4] ?? '').toLowerCase()
  const attr = dplJsonCellToAttrObject(r[5]) ?? {}
  return {
    content: String(r[0] ?? ''),
    scheduleNumber: String(r[1] ?? ''),
    addBack: tagStr === 'true' || tagStr === '1' || tagStr === 'yes',
    current_year: Number.isNaN(thisVal) ? 0 : thisVal,
    prior_year: Number.isNaN(priorVal) ? 0 : priorVal,
    tag: tagStr,
    attr,
  }
}

/** Rows from pasted JSON; when non-null, replaces prop `importData` in the Import section. */
const pastedImportGroupedData = ref<GroupedDataItem[] | null>(null)

/**
 * Pasted DPL: each row is length 6 — [content, note, currentYear, priorYear, lineStyle, meta].
 * After filter, meta (row[5]) is an object. tag uses that meta object; attr only carries categoryName.
 */
function importedDplRowToGroupedItem(row: unknown[]): GroupedDataItem {
  const meta = dplJsonCellToAttrObject(row[5])
  const lineStyle = row[4]

  const tag: string | Record<string, unknown> =
    meta != null ? meta : String(lineStyle ?? '')

  const categoryName = meta && typeof meta.categoryName === 'string' ? meta.categoryName : ''

  return {
    content: String(row[0] ?? '').trim(),
    scheduleNumber: '',
    addBack: false,
    current_year: dplImportAmountToNumber(row[2]),
    prior_year: dplImportAmountToNumber(row[3]),
    tag,
    attr: { categoryName },
  }
}

interface ParsedImportedDplResult {
  items: GroupedDataItem[]
  profitBeforeTaxCurrentYear: number
}

function parseImportedDplJsonToGroupedItems(jsonStr: string): ParsedImportedDplResult {
  const trimmed = jsonStr.trim()
  if (!trimmed)
    throw new Error('Empty DPL data')

  const parsed = JSON.parse(trimmed) as unknown
  if (!Array.isArray(parsed))
    throw new Error('DPL data must be a JSON array')

  const rows = parsed.filter((row): row is unknown[] => Array.isArray(row))

  // find the row that has the category name "Profit before tax"
  const profitBeforeTaxRow = rows.find((row) => {
    const obj = dplJsonCellToAttrObject(row[5])
    const categoryName = typeof obj?.categoryName === 'string' ? obj.categoryName.trim().toUpperCase() : ''
    return categoryName === 'PROFIT BEFORE TAX'
  })
  // get the current year amount of the profit before tax row
  const profitBeforeTaxCurrentYear = profitBeforeTaxRow
    ? dplImportAmountToNumber(profitBeforeTaxRow[2])
    : 0

  // get the items that are display name or sub account
  const items = rows
    .filter((row) => {
      const obj = dplJsonCellToAttrObject(row[5])
      return obj != null && (obj.isDisplayName === true || obj.isSubAccount === true)
    })
    .map(importedDplRowToGroupedItem)

  return {
    items,
    profitBeforeTaxCurrentYear,
  }
}

function applyProfitBeforeTaxCurrentYear(value: number) {
  PROFIT_LOSS_GROUPED_ITEM.current_year = value

  const lastRow = mannualInputData.value[mannualInputData.value.length - 1]
  if (lastRow?.attr?.isCalculated === true)
    lastRow.current_year = value
}

function onImportDPL() {
  try {
    const { items, profitBeforeTaxCurrentYear } = parseImportedDplJsonToGroupedItems(importDPLData.value)
    console.log('onImportDPL', items)

    pastedImportGroupedData.value = items
    applyProfitBeforeTaxCurrentYear(profitBeforeTaxCurrentYear)
    showImportDPLDialog.value = false
    showToast(`Imported ${items.length} row(s).`, 'success')
  }
  catch (error) {
    console.error('Error parsing DPL data', error)
    showToast('Invalid DPL JSON. Check format and try again.', 'error')
  }
}

const EMPTY_GROUPED_ITEM: GroupedDataItem = {
  content: '',
  scheduleNumber: '',
  addBack: false,
  current_year: 0,
  prior_year: 0,
  tag: '',
  attr: { categoryName: 'OTHERS' },
}

const PROFIT_LOSS_GROUPED_ITEM: GroupedDataItem = {
  content: 'Profit/ (Loss) before tax',
  scheduleNumber: '',
  addBack: false,
  current_year: 0,
  prior_year: 0,
  tag: 'Profit before tax',
  attr: {
    categoryName: 'OTHERS',
    isCalculated: true,
  },
}

function createDefaultMannualRows(): GroupedDataItem[] {
  return [
    { ...EMPTY_GROUPED_ITEM, attr: { ...EMPTY_GROUPED_ITEM.attr } },
    { ...PROFIT_LOSS_GROUPED_ITEM, attr: { ...PROFIT_LOSS_GROUPED_ITEM.attr } },
  ]
}

const props = withDefaults(
  defineProps<{
    /** API data: Import data, each row is [item name, Note, this, last, tag, attr] */
    importData?: DPLRow[]
    /** client data, used for currency label (e.g. "2022 HKD") */
    clientData?: Content | null
    /** basic info, used for Aqua request (company/year labels) */
    basicInformationData: BasicInformationData
    /** resolved currency object by currency uuid */
    clientCurrency?: { currency: string; symbol: string; uuid: string } | null
  }>(),
  { importData: () => [], clientData: null, clientCurrency: null },
)

const currency = computed(() => {
  const name = props.clientCurrency?.currency
  if (typeof name === 'string' && name.trim() !== '')
    return name
  return props.clientData?.currency ?? 'HKD'
})

/** Import: pasted JSON overrides API `importData` until cleared. */
const importGroupedData = computed<GroupedDataItem[]>(() => {
  if (pastedImportGroupedData.value !== null)
    return pastedImportGroupedData.value
  return (props.importData ?? []).map(dplRowToGroupedItem)
})

/** Manual input: use GroupedDataItem, last row is fixed to Profit/(Loss) before tax */
const mannualInputData = ref<GroupedDataItem[]>([
  { ...EMPTY_GROUPED_ITEM },
  { ...PROFIT_LOSS_GROUPED_ITEM },
])

function splitLegacyRows(rows: GroupedDataItem[]): DPLGroupedData {
  const importedData: GroupedDataItem[] = []
  const manualRows: GroupedDataItem[] = []
  for (const item of rows) {
    const row: GroupedDataItem = { ...item, attr: { ...(item.attr ?? {}) } }
    const categoryName = String(row.attr?.categoryName ?? '').trim().toUpperCase()
    if (categoryName === 'OTHERS')
      manualRows.push(row)
    else
      importedData.push(row)
  }
  return { importedData, mannualInputData: manualRows }
}

function ensureProfitLossRow(rows: GroupedDataItem[]): GroupedDataItem[] {
  const next = rows.map(item => ({ ...item, attr: { ...(item.attr ?? {}) } }))
  const hasProfitLossRow = next.some(r => r.attr?.isCalculated === true)
  if (!hasProfitLossRow)
    next.push({ ...PROFIT_LOSS_GROUPED_ITEM, attr: { ...PROFIT_LOSS_GROUPED_ITEM.attr } })
  return next.length ? next : createDefaultMannualRows()
}

function setGroupedData(data?: DPLGroupedData | GroupedDataItem[] | null) {
  if (!data) {
    pastedImportGroupedData.value = null
    mannualInputData.value = createDefaultMannualRows()
    return
  }

  if (Array.isArray(data)) {
    const split = splitLegacyRows(data)
    pastedImportGroupedData.value = split.importedData.length ? split.importedData : null
    mannualInputData.value = ensureProfitLossRow(split.mannualInputData)
    return
  }

  const importedRows = Array.isArray(data.importedData) ? data.importedData : []
  const manualRows = Array.isArray(data.mannualInputData) ? data.mannualInputData : []
  pastedImportGroupedData.value = importedRows.length
    ? importedRows.map(item => ({ ...item, attr: { ...(item.attr ?? {}) } }))
    : null
  mannualInputData.value = ensureProfitLossRow(manualRows)
}

function addRow(afterIndex: number) {
  const len = mannualInputData.value.length
  const insertAt = afterIndex >= len - 1 ? len - 1 : afterIndex + 1
  mannualInputData.value.splice(insertAt, 0, { ...EMPTY_GROUPED_ITEM })
}

function removeOthersRow(index: number) {
  if (mannualInputData.value.length <= 2) return
  if (index === mannualInputData.value.length - 1) return
  mannualInputData.value.splice(index, 1)
}

function getProfitLossContentByValue(value: number): string {
  if (Number.isNaN(value))
    return 'Profit/ (Loss) before tax'
  return value >= 0 ? 'Loss before tax' : 'Profit before tax'
}

function syncProfitLossRowContent() {
  const lastRow = mannualInputData.value[mannualInputData.value.length - 1]
  if (!lastRow || lastRow.attr?.isCalculated !== true)
    return
  lastRow.content = getProfitLossContentByValue(lastRow.current_year)
}

/** last row (Profit/Loss) Content displays: based on the current_year amount */
const profitLossLabel = computed(() => {
  const rows = mannualInputData.value
  if (!rows.length) return 'Profit/ (Loss) before tax'
  const last = rows[rows.length - 1]
  return getProfitLossContentByValue(last.current_year)
})

const isProfitLossRow = (rowIndex: number) => rowIndex === mannualInputData.value.length - 1

const showDeleteRowConfirm = ref(false)
const rowIndexToDelete = ref<number | null>(null)

function openDeleteRowConfirm(index: number) {
  rowIndexToDelete.value = index
  showDeleteRowConfirm.value = true
}

function confirmDeleteRow() {
  if (rowIndexToDelete.value !== null) {
    removeOthersRow(rowIndexToDelete.value)
    rowIndexToDelete.value = null
  }
  showDeleteRowConfirm.value = false
}

function cancelDeleteRow() {
  rowIndexToDelete.value = null
  showDeleteRowConfirm.value = false
}

function handleAmountFocus(rowIndex: number) {
  const row = mannualInputData.value[rowIndex]
  focusedAmountKey.value = `others-${rowIndex}`
  focusedAmountRaw.value = row?.current_year === 0 ? '' : String(row?.current_year ?? '')
}

function handleAmountBlur(rowIndex: number) {
  const row = mannualInputData.value[rowIndex]
  const raw = focusedAmountRaw.value
  if (row) {
    const parsed = Number.parseFloat(parseAmountInput(raw))
    row.current_year = Number.isNaN(parsed) ? 0 : parsed
    if (isProfitLossRow(rowIndex))
      row.content = getProfitLossContentByValue(row.current_year)
  }
  focusedAmountKey.value = null
  focusedAmountRaw.value = ''
}

/** Output payload grouped by source section for clearer restore logic. */
const groupedData = computed<DPLGroupedData>(() => {
  const importedData = importGroupedData.value.map(item => ({ ...item, attr: { ...item.attr } }))
  const manualPayload = mannualInputData.value.map((item) => {
    if (item.attr?.isCalculated === true) {
      return {
        ...item,
        content: getProfitLossContentByValue(item.current_year),
      }
    }
    return { ...item, attr: { ...item.attr } }
  })
  return {
    importedData,
    mannualInputData: manualPayload,
  }
})

watch(
  () => mannualInputData.value.map(row => row.current_year),
  () => {
    syncProfitLossRowContent()
  },
  { immediate: true },
)

function onSaveSelection() {
  console.log('groupedData', groupedData.value)
  // emit('save-grouped-data', groupedData.value)
}
const emit = defineEmits<{ 
  (e: 'save-grouped-data', data: DPLGroupedData): void
  (e: 'update:localDPL', val: string): void
}>()
defineExpose({
  groupedData,
  setGroupedData,
})
</script>

<template>
  <div class="dpl">
    <!-- <VBtn color="primary" size="x-small" @click="onSaveSelection">
      groupedData
    </VBtn> -->
    <div class="dpl-header">
      <h6 class="dpl-title text-h6">Detailed income statement</h6>
      <div class="dpl-header-buttons d-flex gap-2">
        <VBtn color="primary" size="x-small" @click="importDataFromAqua">
          Import from AQUA
        </VBtn>
          <VBtn color="error" size="x-small" :disabled="pastedImportGroupedData === null" @click="onClearImportedData">
            Clear imported data
        </VBtn>
      </div>
    </div>
    <div class="dpl-table-wrap">
      <table class="dpl-table">
        <colgroup>
          <col class="dpl-col-content">
          <col class="dpl-col-sch">
          <col class="dpl-col-add-back">
          <col class="dpl-col-amount">
          <col class="dpl-col-actions">
        </colgroup>
        <thead>
          <tr>
            <th colspan="3" class="dpl-th-group">Context Control</th>
            <th colspan="1" class="dpl-th-group">DR./(CR.)</th>
            <th class="dpl-th-group" />
          </tr>
          <tr>
            <th class="dpl-th">Content</th>
            <th class="dpl-th dpl-th-sch">Sch.</th>
            <th class="dpl-th dpl-th-add-back">Add back</th>
            <th class="dpl-th dpl-th-amount">{{ currency }}</th>
            <th class="dpl-th dpl-th-actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          <!-- Import (from API): display Content / Sch. / Taxable / This, hide last/tag/attr -->
          <tr class="dpl-category-row">
            <td colspan="5" class="dpl-category-cell">
              <span class="dpl-category-name">Import</span>
            </td>
          </tr>
          <tr
            v-for="(row, rowIndex) in importGroupedData"
            :key="`import-${rowIndex}`"
            class="dpl-data-row"
          >
            <td class="dpl-td">
              <span class="dpl-content-text">{{row.content}}</span>
            </td>
            <td class="dpl-td dpl-td-sch">
              <VSelect
                v-model="row.scheduleNumber"
                :items="SCH_OPTIONS"
                density="compact"
                hide-details
                variant="outlined"
                class="dpl-select"
                placeholder=""
              />
            </td>
            <td class="dpl-td dpl-td-add-back">
              <div class="dpl-td-add-back-inner">
                <VSwitch
                  v-model="row.addBack"
                  base-color="error"
                  color="success"
                  hide-details
                  density="compact"
                />
              </div>
            </td>
            <td class="dpl-td dpl-td-amount">
              {{ formatAmountDisplay(String(row.current_year)) }}
            </td>
            <td class="dpl-td-actions" />
          </tr>

          <!-- Others (manual input) -->
          <tr class="dpl-category-row">
            <td colspan="5" class="dpl-category-cell">
              <span class="dpl-category-name">Others</span>
            </td>
          </tr>
          <tr
            v-for="(row, rowIndex) in mannualInputData"
            :key="`others-${rowIndex}`"
            class="dpl-data-row"
          >
            <td class="dpl-td">
              <VTextField
                v-if="!isProfitLossRow(rowIndex)"
                v-model="row.content"
                density="compact"
                hide-details
                variant="outlined"
                class="dpl-input"
              />
              <VTextField
                v-else
                :model-value="profitLossLabel"
                density="compact"
                hide-details
                variant="outlined"
                class="dpl-input"
                readonly
                disabled
              />
            </td>
            <td class="dpl-td dpl-td-sch">
              <VSelect
                v-model="row.scheduleNumber"
                :items="SCH_OPTIONS"
                density="compact"
                hide-details
                variant="outlined"
                class="dpl-select"
                placeholder=""
              />
            </td>
            <td class="dpl-td dpl-td-add-back">
              <div v-if="!isProfitLossRow(rowIndex)" class="dpl-td-add-back-inner">
                <VSwitch
                  v-model="row.addBack"
                  base-color="error"
                  color="success"
                  hide-details
                  density="compact"
                />
              </div>
            </td>
            <td class="dpl-td dpl-td-amount">
              <VTextField
                :model-value="focusedAmountKey === `others-${rowIndex}` ? focusedAmountRaw : (row.current_year === 0 ? '' : formatAmountDisplay(String(row.current_year)))"
                density="compact"
                hide-details
                variant="outlined"
                class="dpl-input dpl-amount-input"
                @update:model-value="(v) => { focusedAmountRaw = v; const n = Number(sanitizeAmountInput(parseAmountInput(v))); if (!Number.isNaN(n)) row.current_year = n }"
                @keydown="onAmountKeydown"
                @focus="handleAmountFocus(rowIndex)"
                @blur="handleAmountBlur(rowIndex)"
              />
            </td>
            <td class="dpl-td-actions dpl-add-delete-cell">
              <div class="dpl-add-delete-cell-inner">
                <VBtn
                  icon
                  size="x-small"
                  color="primary"
                  rounded="circle"
                  @click="addRow(rowIndex)"
                >
                  <i class="ri-add-line" />
                </VBtn>
                <VBtn
                  icon
                  size="x-small"
                  color="error"
                  rounded="circle"
                  :disabled="isProfitLossRow(rowIndex) || mannualInputData.length <= 2"
                  @click="openDeleteRowConfirm(rowIndex)"
                >
                  <i class="ri-delete-bin-line" />
                </VBtn>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmDialog
      v-model="showDeleteRowConfirm"
      header="Confirm Delete"
      text="Are you sure you want to delete this row? This action cannot be undone."
      confirm-button-text="Delete"
      confirm-button-color="error"
      max-width="500"
      @confirm="confirmDeleteRow"
      @cancel="cancelDeleteRow"
    />

    <VDialog v-model="showImportDPLDialog" max-width="500">
      <VCard>
        <div class="d-flex justify-space-between align-center pa-4">
          <span class="text-h6">Import DPL</span>
          <DialogCloseBtn
            variant="text"
            size="default"
            @click="showImportDPLDialog = false"
          />
        </div>
        <VDivider />
        <VCardText>
          <VForm @submit.prevent="onImportDPL">
            <VTextarea
              v-model="importDPLData"
              label="Paste DPL data"
              placeholder="Paste DPL data"
              density="compact"
              hide-details
              rows="10"
              no-resize
              :rules="[requiredValidator]"
              class="required-field"
            />
            <div class="d-flex justify-end mt-4">
              <VBtn type="submit" color="primary" size="small">
                Import
              </VBtn>
            </div>
          </VForm>
        </VCardText>
      </VCard>
    </VDialog>
  </div>
</template>

<style lang="scss" scoped>
.required-field :deep(.v-field__field label::before),
.required-field :deep(.v-label::before) {
  content: "*";
  color: rgb(var(--v-theme-error));
  margin-left: 1px;
}
.dpl {
  padding: 1rem 1rem 0 1rem;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.dpl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.dpl-title {
  color: rgb(var(--v-theme-primary));
  font-weight: 700;
  flex-shrink: 0;
  text-wrap: nowrap;
}

.dpl-table-wrap {
  flex: 1 1 auto;
  overflow: auto;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 4px;
}

.dpl-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.dpl-table th,
.dpl-table td {
  border-right: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.dpl-table th:last-child,
.dpl-table td:last-child {
  border-right: none;
}

.dpl-table {
  :deep(.v-input--density-compact) { --v-input-control-height: 28px; }
  :deep(.v-input) { --v-input-control-height: 28px; }

  :deep(.v-field) {
    --v-field-input-padding-top: 1px;
    --v-field-input-padding-bottom: 1px;
    --v-field-padding-start: 6px;
    --v-field-padding-end: 6px;
    min-height: 24px !important;
    font-size: 0.6875rem;
  }

  :deep(.v-field__input) {
    min-height: 24px !important;
    padding-block: 1px !important;
    font-size: 0.6875rem;
  }
}

.dpl-th-group {
  padding: 5px 8px;
  font-weight: 600;
  font-size: 0.7rem;
  color: rgba(var(--v-theme-on-surface), 0.7);
  text-decoration: underline;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.dpl-th {
  padding: 3px 8px;
  font-weight: 600;
  font-size: 0.7rem;
  text-align: left;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.dpl-col-content { min-width: 120px; width: auto; }
.dpl-col-sch { width: 80px; }
.dpl-col-add-back { width: 80px; }
.dpl-col-amount { width: 100px; }
.dpl-col-actions { width: 90px; }

.dpl-th-sch { width: 80px; text-align: center; }
.dpl-td-sch { width: 80px; vertical-align: middle; }
.dpl-th-add-back { width: 80px; text-align: center; }
.dpl-td-add-back { width: 80px; text-align: center; vertical-align: middle; }
.dpl-td-add-back-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 28px;
}
.dpl-th-amount { width: 100px; text-align: center; }
.dpl-td-amount { width: 100px; text-align: right; vertical-align: middle; }

.dpl-th-actions { width: 90px; text-align: center; }
.dpl-td-actions {
  width: 90px;
  text-align: center;
  vertical-align: middle;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.dpl-td-sch :deep(.v-select) { max-width: 100%; }
.dpl-td-sch :deep(.v-field) { min-width: 0; }
.dpl-td-add-back :deep(.v-switch) { min-height: 28px; }

.dpl-td {
  vertical-align: middle;
  padding: 1px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  min-height: 28px;
  box-sizing: border-box;
}

.dpl-amount-input :deep(.v-field__input) {
  text-align: right;
}

.dpl-content-text {
  font-size: 0.7rem;
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.7);
  display: block;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.2;
}

.dpl-category-row td {
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.dpl-category-cell {
  padding: 5px 8px;
  font-weight: 700;
  font-size: 0.7rem;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.dpl-category-name {
  white-space: normal;
  word-break: normal;
  overflow-wrap: normal;
  word-wrap: normal;
}

.dpl-data-row td {
  vertical-align: middle;
}

.dpl-add-delete-cell {
  padding: 0 !important;
  min-height: 28px !important;
  vertical-align: middle;
}

.dpl-add-delete-cell-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 38px;
  padding: 2px 8px;
  box-sizing: border-box;
}

.dpl-add-delete-cell-inner :deep(.v-btn) {
  margin: 0;
  font-size: 0.75rem;
  min-width: 26px;
  width: 26px;
  min-height: 26px;
  height: 26px;
  padding: 0;
  flex-shrink: 0;
}

.dpl-add-delete-cell-inner :deep(.v-btn i) {
  font-size: 0.875rem;
}

.dpl-footer {
  margin-top: 1rem;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}
</style>
