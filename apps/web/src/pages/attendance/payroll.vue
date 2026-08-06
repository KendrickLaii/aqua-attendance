<script setup lang="ts">
import { deletePayrollRecord, generatePayroll, getPayrollStats, listPayrollRecordsWithTotal, updatePayrollRecord } from '@/api/attendance/payroll'
import type { PayrollRecord, PayrollStats } from '@/api/attendance/payroll'
import { listSummariesWithTotal, listSummaryOverview } from '@/api/attendance/summaries'
import type { AttendanceSummary } from '@/api/attendance/summaries'
import { listUnits } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import AutoCheckoutChip from '@/components/attendance/AutoCheckoutChip.vue'
import SummaryDateCell from '@/components/attendance/SummaryDateCell.vue'
import { formatAttendanceDateTime, isAutoCheckoutSummaryDay } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatPayrollGenerateMessage } from '@/utils/formatGenerateResult'

definePage({ meta: {} })

const { authStore, ensureAccess } = useAttendanceAdminGate()
const {
  yearMonth,
  parsed: parsedYearMonth,
  monthDateRange,
  monthLabel,
  toCurrentMonth,
} = useYearMonth()
const {
  yearMonth: stepMonth,
  parsed: stepParsedMonth,
  monthDateRange: stepMonthDateRange,
  monthLabel: stepMonthLabel,
  toCurrentMonth: toStepCurrentMonth,
} = useYearMonth()
const {
  page,
  pageSize,
  pageSizeOptions,
  totalCount,
  totalPages,
  listCaption: pagedListCaption,
  resetPage,
} = usePagedList({ pageSize: 40 })

const records = ref<PayrollRecord[]>([])
const payrollStats = ref<PayrollStats | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filterStatus = ref('')
const filterUnitType = ref('staff')
const generating = ref(false)
const generateError = ref('')
const generateSuccess = ref<{ title: string; detail?: string; warning?: string } | null>(null)
const deleteDialog = ref(false)
const deleteTarget = ref<PayrollRecord | null>(null)

const selectedRecord = ref<PayrollRecord | null>(null)
const summaries = ref<AttendanceSummary[]>([])
const detailTotalCount = ref(0)

// Stepper workflow state (configure = Units+Month, result = invoice cards)
const step = ref('configure')
const stepUnits = ref<Unit[]>([])
const stepUnitsLoading = ref(false)
const stepUnitsError = ref('')
const stepSelectedIds = ref<string[]>([])
const stepSearch = ref('')
/** Default: only staff who have attendance summaries for the payroll month. */
const stepShowAllStaff = ref(false)
const stepStaffWithSummariesCount = ref(0)
const generatedRecords = ref<PayrollRecord[]>([])
const viewMode = ref<'wizard' | 'records'>('wizard')

const isDetailView = computed(() => !!selectedRecord.value)

const statusOptions = [
  { title: 'All statuses', value: '' },
  { title: 'Draft', value: 'draft' },
  { title: 'Calculated', value: 'calculated' },
  { title: 'Approved', value: 'approved' },
  { title: 'Paid', value: 'paid' },
  { title: 'Cancelled', value: 'cancelled' },
]

const statusColorMap: Record<string, string> = {
  draft: 'grey',
  calculated: 'info',
  approved: 'success',
  paid: 'primary',
  cancelled: 'error',
}


const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  if (isDetailView.value && selectedRecord.value)
    return `${selectedRecord.value.unit_name || selectedRecord.value.unit_code} · ${monthLabel.value}`

  if (viewMode.value === 'wizard') {
    if (step.value === 'result')
      return `${stepMonthLabel.value} · ${generatedRecords.value.length} generated`

    return `${stepMonthLabel.value} · ${stepSelectedCount.value} of ${stepUnits.value.length} staff selected`
  }

  return `${monthLabel.value} · ${totalCount.value} record${totalCount.value === 1 ? '' : 's'}`
})

const recordsStatCards = computed(() => {
  const stats = payrollStats.value
  const gross = safeNumber(stats?.total_gross_pay ?? 0)
  const net = safeNumber(stats?.total_net_pay ?? 0)
  const approved = stats?.approved ?? 0
  const paid = stats?.paid ?? 0
  const pending = stats?.pending ?? 0

  return [
    {
      label: 'Payroll slips',
      value: String(totalCount.value),
      hint: listCaption.value || 'matching filters',
      icon: 'ri-file-list-3-line',
      color: 'primary',
    },
    {
      label: 'Gross pay',
      value: formatCurrency(gross),
      hint: 'all matching',
      icon: 'ri-money-dollar-circle-line',
      color: 'info',
    },
    {
      label: 'Net pay',
      value: formatCurrency(net),
      hint: 'all matching',
      icon: 'ri-wallet-3-line',
      color: 'success',
    },
    {
      label: 'Paid',
      value: String(paid),
      hint: `${approved} approved · ${pending} pending`,
      icon: 'ri-checkbox-circle-line',
      color: 'secondary',
    },
  ]
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  return pagedListCaption(records.value.length)
})


const detailTotals = computed(() => {
  const regular = summaries.value.reduce((sum, s) => sum + safeNumber(s.regular_hours), 0)
  const regularSlots = summaries.value.reduce((sum, s) => sum + safeNumber(s.regular_slots), 0)
  const overtime = summaries.value.reduce((sum, s) => sum + safeNumber(s.overtime_hours), 0)
  const otSlots = summaries.value.reduce((sum, s) => sum + safeNumber(s.ot_slots), 0)
  const autoCheckoutDays = summaries.value.filter(s => isAutoCheckoutSummaryDay(s)).length

  return { regular, regularSlots, overtime, otSlots, days: summaries.value.length, autoCheckoutDays }
})



const stepFilteredUnits = computed(() => {
  const q = stepSearch.value.trim().toLowerCase()
  if (!q)
    return stepUnits.value

  return stepUnits.value.filter(u =>
    u.full_name.toLowerCase().includes(q) || u.code.toLowerCase().includes(q),
  )
})

const stepAllSelected = computed({
  get: () => stepUnits.value.length > 0 && stepSelectedIds.value.length === stepUnits.value.length,
  set: (val: boolean) => {
    stepSelectedIds.value = val ? stepUnits.value.map(u => u.id) : []
  },
})

const stepSelectedCount = computed(() => stepSelectedIds.value.length)

onMounted(async () => {
  if (!(await ensureAccess()))
    return

  toCurrentMonth()
  toStepCurrentMonth()
  await loadRecords()
  if (viewMode.value === 'wizard')
    loadStepUnits()
})

watch([yearMonth, filterStatus, filterUnitType], () => {
  selectedRecord.value = null
  summaries.value = []
  loadRecords(true, true)
})

watch(pageSize, () => {
  resetPage()
  loadRecords(true)
})

async function loadRecords(isRefresh = false, shouldResetPage = false) {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return

  if (shouldResetPage)
    resetPage()
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const [result, stats] = await Promise.all([
      listPayrollRecordsWithTotal({
        status: filterStatus.value || undefined,
        unit_type: filterUnitType.value || undefined,
        year: parsed.year,
        month: parsed.month,
        page: page.value,
        page_size: pageSize.value,
      }),
      getPayrollStats({
        status: filterStatus.value || undefined,
        unit_type: filterUnitType.value || undefined,
        year: parsed.year,
        month: parsed.month,
      }),
    ])

    records.value = result.items
    totalCount.value = result.total
    payrollStats.value = stats
  }
  catch (e) {
    console.error('Failed to load payroll records', e)
    loadError.value = formatApiError(e, 'Failed to load payroll records. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

async function loadDetail(isRefresh = false) {
  const range = monthDateRange.value
  if (!range || !selectedRecord.value)
    return

  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listSummariesWithTotal({
      unit_id: selectedRecord.value.unit_id,
      date_from: range.date_from,
      date_to: range.date_to,
      page: 1,
      page_size: 100,
    })

    summaries.value = result.items
    detailTotalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load payroll detail', e)
    loadError.value = formatApiError(e, 'Failed to load daily summaries for this record. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

function openDetail(record: PayrollRecord) {
  selectedRecord.value = record
  summaries.value = []
  loadDetail()
}

function onCardAdjChange(record: PayrollRecord) {
  const adj1 = Number(record.adjustment_1) || 0
  const adj2 = Number(record.adjustment_2) || 0
  const gross = record.base_salary + record.overtime_pay + record.holiday_pay + adj1
  const net = gross + adj2

  record.gross_pay = gross
  record.net_pay = net
  updatePayrollRecord(record.id, {
    adjustment_1: adj1,
    adjustment_2: adj2,
    adjustment_1_remark: record.adjustment_1_remark || null,
    adjustment_2_remark: record.adjustment_2_remark || null,
    gross_pay: gross,
    net_pay: net,
  }).then(updated => {
    record.adjustment_1 = updated.adjustment_1
    record.adjustment_2 = updated.adjustment_2
    record.adjustment_1_remark = updated.adjustment_1_remark
    record.adjustment_2_remark = updated.adjustment_2_remark
    record.gross_pay = updated.gross_pay
    record.net_pay = updated.net_pay
  }).catch(e => {
    console.error('Failed to update adjustments', e)
  })
}

/** Display-only currency formatting for adj inputs; record values stay numeric. */
type AdjField = 'adjustment_1' | 'adjustment_2'
const focusedAdjKey = ref<string | null>(null)
const focusedAdjRaw = ref('')

function adjFocusKey(record: PayrollRecord, field: AdjField) {
  return `${record.id}:${field}`
}

function parseCurrencyInput(display: string | number | null | undefined) {
  const s = String(display ?? '').replace(/,/g, '').trim()
  if (s === '' || s === '-' || s === '.' || s === '-.')
    return 0
  const n = Number(s)
  return Number.isFinite(n) ? n : 0
}

function adjDisplayValue(record: PayrollRecord, field: AdjField) {
  if (focusedAdjKey.value === adjFocusKey(record, field))
    return focusedAdjRaw.value
  return formatCurrency(record[field])
}

function onAdjFocus(record: PayrollRecord, field: AdjField) {
  focusedAdjKey.value = adjFocusKey(record, field)
  const n = Number(record[field])
  focusedAdjRaw.value = Number.isFinite(n) ? String(n) : '0'
}

function onAdjInput(record: PayrollRecord, field: AdjField, v: string | number | null) {
  focusedAdjRaw.value = v == null ? '' : String(v)
  record[field] = parseCurrencyInput(focusedAdjRaw.value)
  onCardAdjChange(record)
}

function onAdjBlur(record: PayrollRecord, field: AdjField) {
  record[field] = parseCurrencyInput(focusedAdjRaw.value)
  focusedAdjKey.value = null
  focusedAdjRaw.value = ''
}

function backToOverview() {
  selectedRecord.value = null
  summaries.value = []
}

function refresh() {
  if (selectedRecord.value)
    loadDetail(true)
  else
    loadRecords(true)
}


async function updateStatus(record: PayrollRecord, newStatus: string) {
  try {
    await updatePayrollRecord(record.id, { status: newStatus })
    record.status = newStatus as PayrollRecord['status']
  }
  catch (e) {
    console.error('Failed to update status', e)
    loadError.value = formatApiError(e, 'Could not update status')
  }
}

function openDeleteDialog(record: PayrollRecord) {
  deleteTarget.value = record
  deleteDialog.value = true
}

function closeDeleteDialog() {
  deleteDialog.value = false
  deleteTarget.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value)
    return
  try {
    await deletePayrollRecord(deleteTarget.value.id)
    closeDeleteDialog()
    await loadRecords(true)
  }
  catch (e) {
    console.error('Failed to delete record', e)
    loadError.value = formatApiError(e, 'Could not delete record')
  }
}

function resetWizard() {
  step.value = 'configure'
  stepMonth.value = yearMonth.value
  stepSearch.value = ''
  stepUnits.value = []
  stepSelectedIds.value = []
  stepUnitsError.value = ''
  stepShowAllStaff.value = false
  stepStaffWithSummariesCount.value = 0
  generateError.value = ''
  generateSuccess.value = null
  generatedRecords.value = []
}

function showWizard() {
  resetWizard()
  viewMode.value = 'wizard'
  selectedRecord.value = null
  loadStepUnits()
  summaries.value = []
}

function showRecords() {
  viewMode.value = 'records'
  loadRecords(true, true)
}

async function loadStepUnits() {
  stepUnitsLoading.value = true
  stepUnitsError.value = ''
  try {
    const range = stepMonthDateRange.value
    if (!range) {
      stepUnits.value = []
      stepSelectedIds.value = []
      stepStaffWithSummariesCount.value = 0
      stepUnitsError.value = 'Select a valid month'

      return
    }

    const [allStaff, overview] = await Promise.all([
      listUnits({ unit_type: 'staff', page_size: 200 }),
      listSummaryOverview({
        date_from: range.date_from,
        date_to: range.date_to,
        unit_type: 'staff',
        page: 1,
        page_size: 200,
      }),
    ])

    const withSummaryIds = new Set(overview.items.map(item => item.unit_id))
    stepStaffWithSummariesCount.value = withSummaryIds.size

    const sorted = [...allStaff].sort((a, b) => a.full_name.localeCompare(b.full_name))
    stepUnits.value = stepShowAllStaff.value
      ? sorted
      : sorted.filter(u => withSummaryIds.has(u.id))

    // Keep prior selection when possible; otherwise select everyone in the visible list
    const visibleIds = new Set(stepUnits.value.map(u => u.id))
    const kept = stepSelectedIds.value.filter(id => visibleIds.has(id))
    stepSelectedIds.value = kept.length > 0
      ? kept
      : stepUnits.value.map(u => u.id)
  }
  catch (e) {
    console.error('Failed to load units for payroll generation', e)
    stepUnitsError.value = formatApiError(e, 'Failed to load units')
  }
  finally {
    stepUnitsLoading.value = false
  }
}

watch(step, newStep => {
  if (newStep === 'configure')
    loadStepUnits()
})

watch([stepMonth, stepShowAllStaff], () => {
  if (viewMode.value === 'wizard' && step.value === 'configure')
    loadStepUnits()
})

function toggleStepUnit(id: string) {
  const idx = stepSelectedIds.value.indexOf(id)
  if (idx === -1)
    stepSelectedIds.value.push(id)
  else
    stepSelectedIds.value.splice(idx, 1)
}

async function handleGenerate() {
  const parsed = stepParsedMonth.value
  if (!parsed) {
    generateError.value = 'Select a valid month'

    return
  }
  if (stepSelectedCount.value === 0) {
    generateError.value = 'Select at least one unit'

    return
  }

  const { year, month } = parsed
  const idsToSend = stepAllSelected.value ? undefined : stepSelectedIds.value

  generating.value = true
  generateError.value = ''
  generateSuccess.value = null
  generatedRecords.value = []
  try {
    const generateResult = await generatePayroll(year, month, 'staff', idsToSend)

    generateSuccess.value = formatPayrollGenerateMessage(generateResult, year, month)
    filterUnitType.value = 'staff'
    yearMonth.value = stepMonth.value

    const result = await listPayrollRecordsWithTotal({
      unit_type: 'staff',
      year,
      month,
      page: 1,
      page_size: 200,
    })

    generatedRecords.value = result.items.filter(r =>
      idsToSend ? idsToSend.includes(r.unit_id) : true,
    )
    viewMode.value = 'wizard'
    step.value = 'result'
  }
  catch (e) {
    console.error('Failed to generate payroll records', e)
    generateError.value = formatApiError(e, 'Could not generate payroll records')
  }
  finally {
    generating.value = false
  }
}

function statusLabel(s: AttendanceSummary) {
  if (s.is_holiday)
    return 'Holiday'
  if (s.is_weekend)
    return 'Weekend'

  return s.is_complete ? 'Complete' : 'Incomplete'
}

function statusColor(s: AttendanceSummary) {
  if (s.is_holiday || s.is_weekend)
    return 'info'

  return s.is_complete ? 'success' : 'warning'
}

function summaryStatusIcon(s: AttendanceSummary) {
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

function statusIcon(status: string) {
  switch (status) {
    case 'draft':
      return 'ri-draft-line'
    case 'calculated':
      return 'ri-calculator-line'
    case 'approved':
      return 'ri-checkbox-circle-line'
    case 'paid':
      return 'ri-money-dollar-circle-line'
    case 'cancelled':
      return 'ri-close-circle-line'
    default:
      return 'ri-file-list-line'
  }
}

function formatHours(h: number) {
  return Number.isFinite(h) ? h.toFixed(2) : '-'
}

function safeNumber(value: number) {
  return Number.isFinite(value) ? value : 0
}

function formatCurrency(n: number | null | undefined) {
  const value = Number.isFinite(n) ? Number(n) : 0

  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
</script>

<template>
  <VContainer>
    <!-- Header -->
    <VRow
      class="mb-4"
      align="center"
    >
      <VCol>
        <h1 class="text-h5 font-weight-bold">
          Payroll
        </h1>
        <p class="text-subtitle-2 text-medium-emphasis mb-0">
          {{ pageSubtitle }}
        </p>
      </VCol>
      <VCol
        cols="12"
        md="auto"
        class="d-flex flex-wrap gap-2 justify-md-end"
      >
        <VBtn
          :variant="viewMode === 'wizard' ? 'flat' : 'tonal'"
          color="primary"
          prepend-icon="ri-magic-line"
          @click="showWizard"
        >
          New run
        </VBtn>
        <VBtn
          :variant="viewMode === 'records' ? 'flat' : 'tonal'"
          color="primary"
          prepend-icon="ri-file-list-3-line"
          @click="showRecords"
        >
          Records
        </VBtn>
      </VCol>
    </VRow>

    <VAlert
      v-if="generateSuccess"
      type="success"
      variant="tonal"
      density="compact"
      class="mb-4"
      closable
      :title="generateSuccess.title"
      :text="generateSuccess.detail"
      @click:close="generateSuccess = null"
    />

    <VAlert
      v-if="generateSuccess?.warning"
      type="warning"
      variant="tonal"
      density="compact"
      class="mb-4"
      title="Attendance summaries may be out of date"
      :text="generateSuccess.warning"
    />

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      {{ loadError }}
    </VAlert>

    <!-- Wizard mode -->
    <template v-if="viewMode === 'wizard' && !isDetailView">
      <VCard class="payroll-wizard">
        <div class="payroll-steps">
          <button
            type="button"
            class="payroll-step"
            :class="{ 'payroll-step--active': step === 'configure' }"
            @click="step = 'configure'"
          >
            <VIcon
              icon="ri-settings-3-line"
              size="20"
            />
            <span>Configure</span>
          </button>
          <VIcon
            icon="ri-arrow-right-s-line"
            size="18"
            class="payroll-steps-arrow text-medium-emphasis"
          />
          <button
            type="button"
            class="payroll-step"
            :class="{ 'payroll-step--active': step === 'result' }"
            @click="step = 'result'"
          >
            <VIcon
              icon="ri-file-list-3-line"
              size="20"
            />
            <span>Result</span>
          </button>
        </div>
        <VDivider />

        <!-- Step 1: Configure -->
        <div v-show="step === 'configure'">
            <div class="pa-4 pa-md-6">
              <div class="d-flex align-center gap-3 mb-6">
                <VAvatar
                  color="primary"
                  variant="tonal"
                  rounded
                >
                  <VIcon icon="ri-settings-3-line" />
                </VAvatar>
                <div>
                  <h2 class="text-h6 mb-0">
                    Configure payroll run
                  </h2>
                  <p class="text-body-2 text-medium-emphasis mb-0">
                    Pick staff and month, then generate pay slips from attendance summaries.
                  </p>
                </div>
              </div>

              <VAlert
                v-if="generateError"
                type="error"
                variant="tonal"
                density="compact"
                class="mb-4"
              >
                {{ generateError }}
              </VAlert>

              <VCard
                variant="outlined"
                class="mb-4"
              >
                <VCardItem>
                  <template #prepend>
                    <VAvatar
                      color="primary"
                      variant="tonal"
                      size="36"
                      rounded
                    >
                      <VIcon
                        icon="ri-group-line"
                        size="20"
                      />
                    </VAvatar>
                  </template>
                  <VCardTitle class="text-subtitle-1">
                    Staff units
                  </VCardTitle>
                  <VCardSubtitle>
                    {{ stepUnits.length }} shown · {{ stepSelectedCount }} selected
                    <template v-if="!stepShowAllStaff">
                      · {{ stepStaffWithSummariesCount }} with summaries this month
                    </template>
                  </VCardSubtitle>
                </VCardItem>
                <VCardText>
                  <div class="d-flex align-center gap-3 mb-3 flex-wrap">
                    <VTextField
                      v-model="stepSearch"
                      label="Search by name or code"
                      density="compact"
                      prepend-inner-icon="ri-search-line"
                      clearable
                      hide-details
                      style="max-inline-size: 280px;"
                    />
                    <VCheckbox
                      v-model="stepAllSelected"
                      label="Select all"
                      density="compact"
                      hide-details
                      color="primary"
                    />
                    <VCheckbox
                      v-model="stepShowAllStaff"
                      label="Show all staff"
                      density="compact"
                      hide-details
                      color="secondary"
                    />
                  </div>

                  <VProgressLinear
                    v-if="stepUnitsLoading"
                    indeterminate
                    color="primary"
                    class="mb-2"
                  />
                  <VAlert
                    v-else-if="stepUnitsError"
                    type="error"
                    variant="tonal"
                    density="compact"
                    class="mb-2"
                  >
                    {{ stepUnitsError }}
                  </VAlert>

                  <div class="unit-list">
                    <VListItem
                      v-for="u in stepFilteredUnits"
                      :key="u.id"
                      :title="u.full_name"
                      :subtitle="u.code"
                      density="comfortable"
                      class="unit-list-item"
                      :active="stepSelectedIds.includes(u.id)"
                      color="primary"
                      @click="toggleStepUnit(u.id)"
                    >
                      <template #prepend>
                        <VCheckbox
                          :model-value="stepSelectedIds.includes(u.id)"
                          density="comfortable"
                          hide-details
                          color="primary"
                          @click.stop="toggleStepUnit(u.id)"
                        />
                      </template>
                      <template #append>
                        <VChip
                          size="x-small"
                          variant="tonal"
                          color="primary"
                          prepend-icon="ri-user-line"
                          label
                        >
                          Staff
                        </VChip>
                      </template>
                    </VListItem>
                    <div
                      v-if="!stepUnitsLoading && stepFilteredUnits.length === 0"
                      class="text-center text-medium-emphasis py-8"
                    >
                      <template v-if="!stepShowAllStaff && stepSearch.trim() === ''">
                        No staff with summaries for {{ stepMonthLabel }}.
                        Generate Summaries first, or enable Show all staff.
                      </template>
                      <template v-else>
                        No staff units found.
                      </template>
                    </div>
                  </div>
                </VCardText>
              </VCard>

              <VCard
                variant="outlined"
                class="mb-4"
              >
                <VCardItem>
                  <template #prepend>
                    <VAvatar
                      color="info"
                      variant="tonal"
                      size="36"
                      rounded
                    >
                      <VIcon
                        icon="ri-calendar-line"
                        size="20"
                      />
                    </VAvatar>
                  </template>
                  <VCardTitle class="text-subtitle-1">
                    Payroll month
                  </VCardTitle>
                  <VCardSubtitle>
                    Summaries for this month are aggregated into each pay slip
                  </VCardSubtitle>
                </VCardItem>
                <VCardText>
                  <div class="d-flex align-center gap-3 flex-wrap">
                    <VTextField
                      v-model="stepMonth"
                      label="Month"
                      type="month"
                      density="compact"
                      prepend-inner-icon="ri-calendar-event-line"
                      hide-details
                      style="max-inline-size: 220px;"
                    />
                    <VChip
                      color="primary"
                      variant="tonal"
                      prepend-icon="ri-group-line"
                      label
                    >
                      {{ stepSelectedCount }} staff
                    </VChip>
                    <VChip
                      color="info"
                      variant="tonal"
                      prepend-icon="ri-calendar-line"
                      label
                    >
                      {{ stepMonthLabel }}
                    </VChip>
                  </div>
                </VCardText>
              </VCard>

              <div class="d-flex align-center justify-space-between flex-wrap gap-3 mt-2">
                <div class="text-caption text-medium-emphasis">
                  <VIcon
                    icon="ri-information-line"
                    size="14"
                    class="me-1"
                  />
                  Default list = staff with summaries this month. Only selected staff are generated; approved / paid slips are skipped.
                </div>
                <VBtn
                  color="primary"
                  size="large"
                  :loading="generating"
                  :disabled="stepSelectedCount === 0"
                  prepend-icon="ri-magic-line"
                  @click="handleGenerate"
                >
                  Generate payroll
                </VBtn>
              </div>
            </div>
        </div>

        <!-- Step 2: Results -->
        <div v-show="step === 'result'">
            <div class="pa-4 pa-md-6">
              <div class="d-flex align-center justify-space-between mb-4 flex-wrap gap-3">
                <div class="d-flex align-center gap-3">
                  <VAvatar
                    color="success"
                    variant="tonal"
                    rounded
                  >
                    <VIcon icon="ri-file-paper-2-line" />
                  </VAvatar>
                  <div>
                    <h2 class="text-h6 mb-0">
                      Payroll result
                    </h2>
                    <p class="text-body-2 text-medium-emphasis mb-0">
                      {{ stepMonthLabel }} · {{ generatedRecords.length }} slip{{ generatedRecords.length === 1 ? '' : 's' }}
                    </p>
                  </div>
                </div>
                <div class="d-flex gap-2">
                  <VBtn
                    variant="tonal"
                    color="primary"
                    prepend-icon="ri-file-list-3-line"
                    @click="showRecords"
                  >
                    Browse records
                  </VBtn>
                  <VBtn
                    variant="flat"
                    color="primary"
                    prepend-icon="ri-add-line"
                    @click="resetWizard"
                  >
                    New run
                  </VBtn>
                </div>
              </div>

              <VProgressLinear
                v-if="generating"
                indeterminate
                color="primary"
                class="mb-4"
              />

              <VRow v-if="!generating">
                <VCol
                  v-for="record in generatedRecords"
                  :key="record.id"
                  cols="12"
                  md="6"
                  xl="4"
                >
                  <VCard class="payroll-invoice">
                    <VCardItem class="invoice-header">
                      <template #prepend>
                        <VAvatar
                          color="primary"
                          variant="tonal"
                          size="40"
                          rounded
                        >
                          <VIcon icon="ri-user-line" />
                        </VAvatar>
                      </template>
                      <template #title>
                        <div class="d-flex align-center gap-2 flex-wrap">
                          <span class="text-h6 font-weight-bold">
                            {{ record.unit_name || '—' }}
                          </span>
                          <VChip
                            :color="statusColorMap[record.status] ?? 'grey'"
                            size="small"
                            label
                            :prepend-icon="statusIcon(record.status)"
                          >
                            {{ record.status }}
                          </VChip>
                        </div>
                      </template>
                      <template #subtitle>
                        <div class="text-medium-emphasis">
                          {{ record.unit_code || record.unit_id }}
                        </div>
                      </template>
                    </VCardItem>
                    <VDivider />
                    <VCardText class="invoice-body">
                      <div class="d-flex justify-space-between mb-4">
                        <div>
                          <div class="text-caption text-medium-emphasis d-flex align-center gap-1">
                            <VIcon
                              icon="ri-calendar-line"
                              size="14"
                            />
                            Period
                          </div>
                          <div class="font-weight-medium">
                            {{ record.payroll_period_start }} – {{ record.payroll_period_end }}
                          </div>
                        </div>
                        <div class="text-end">
                          <div class="text-caption text-medium-emphasis d-flex align-center justify-end gap-1">
                            <VIcon
                              icon="ri-calendar-check-line"
                              size="14"
                            />
                            Work days
                          </div>
                          <div class="font-weight-medium">
                            {{ record.total_work_days }}
                          </div>
                        </div>
                      </div>

                      <div class="invoice-grid">
                        <div class="invoice-cell">
                          <span class="text-caption text-success d-flex align-center gap-1">
                            <VIcon
                              icon="ri-time-line"
                              size="14"
                            />
                            Regular
                          </span>
                          <span class="font-weight-medium">{{ formatHours(record.total_regular_hours) }} h</span>
                          <span class="text-caption text-medium-emphasis">{{ record.regular_slots }} slots</span>
                        </div>
                        <div class="invoice-cell">
                          <span class="text-caption text-info d-flex align-center gap-1">
                            <VIcon
                              icon="ri-flashlight-line"
                              size="14"
                            />
                            Overtime
                          </span>
                          <span class="font-weight-medium">{{ formatHours(record.total_overtime_hours) }} h</span>
                          <span class="text-caption text-medium-emphasis">{{ record.ot_slots }} slots</span>
                        </div>
                        <div class="invoice-cell">
                          <span class="text-caption text-medium-emphasis d-flex align-center gap-1">
                            <VIcon
                              icon="ri-price-tag-3-line"
                              size="14"
                            />
                            Rate
                          </span>
                          <span class="font-weight-medium">{{ formatCurrency(record.hourly_rate_snapshot) }}/hr</span>
                          <span class="text-caption text-medium-emphasis">OT ×{{ record.ot_multiplier_snapshot ?? 1.5 }}</span>
                        </div>
                      </div>

                      <VDivider class="my-3" />

                      <div class="invoice-line">
                        <span>Base salary</span>
                        <span class="font-weight-medium">{{ formatCurrency(record.base_salary) }}</span>
                      </div>
                      <div class="invoice-line">
                        <span>Overtime pay</span>
                        <span class="font-weight-medium">{{ formatCurrency(record.overtime_pay) }}</span>
                      </div>
                      <div class="invoice-line">
                        <span>Holiday pay</span>
                        <span class="font-weight-medium">{{ formatCurrency(record.holiday_pay) }}</span>
                      </div>
                      <div class="invoice-adj-row">
                        <VTextField
                          v-model="record.adjustment_1_remark"
                          class="invoice-remark"
                          label="Adjustment 1"
                          density="compact"
                          variant="outlined"
                          hide-details
                          @update:model-value="onCardAdjChange(record)"
                        />
                        <VTextField
                          :model-value="adjDisplayValue(record, 'adjustment_1')"
                          class="invoice-adj-amount"
                          density="compact"
                          variant="underlined"
                          hide-details
                          inputmode="decimal"
                          @focus="onAdjFocus(record, 'adjustment_1')"
                          @blur="onAdjBlur(record, 'adjustment_1')"
                          @update:model-value="(v) => onAdjInput(record, 'adjustment_1', v)"
                        />
                      </div>
                      <div class="invoice-line total">
                        <span>Gross pay</span>
                        <span class="font-weight-bold">{{ formatCurrency(record.gross_pay) }}</span>
                      </div>
                      <div class="invoice-adj-row">
                        <VTextField
                          v-model="record.adjustment_2_remark"
                          class="invoice-remark"
                          label="Adjustment 2"
                          density="compact"
                          variant="outlined"
                          hide-details
                          @update:model-value="onCardAdjChange(record)"
                        />
                        <VTextField
                          :model-value="adjDisplayValue(record, 'adjustment_2')"
                          class="invoice-adj-amount"
                          density="compact"
                          variant="underlined"
                          hide-details
                          inputmode="decimal"
                          @focus="onAdjFocus(record, 'adjustment_2')"
                          @blur="onAdjBlur(record, 'adjustment_2')"
                          @update:model-value="(v) => onAdjInput(record, 'adjustment_2', v)"
                        />
                      </div>
                      <div class="invoice-line grand">
                        <span class="d-flex align-center gap-1">
                          <VIcon
                            icon="ri-wallet-3-line"
                            size="18"
                            class="text-primary"
                          />
                          Net pay
                        </span>
                        <span class="text-h6 font-weight-bold text-primary">{{ formatCurrency(record.net_pay) }}</span>
                      </div>
                    </VCardText>
                    <VDivider />
                    <VCardActions class="justify-end">
                      <VBtn
                        v-if="record.status === 'draft' || record.status === 'calculated'"
                        size="small"
                        variant="tonal"
                        color="success"
                        prepend-icon="ri-checkbox-circle-line"
                        @click="updateStatus(record, 'approved')"
                      >
                        Approve
                      </VBtn>
                      <VBtn
                        v-if="record.status === 'approved'"
                        size="small"
                        variant="tonal"
                        color="primary"
                        prepend-icon="ri-money-dollar-circle-line"
                        @click="updateStatus(record, 'paid')"
                      >
                        Pay
                      </VBtn>
                      <VBtn
                        size="small"
                        variant="text"
                        prepend-icon="ri-eye-line"
                        @click="openDetail(record)"
                      >
                        Details
                      </VBtn>
                      <VBtn
                        v-if="authStore.isSuperAdmin"
                        icon
                        size="small"
                        variant="text"
                        color="error"
                        @click.stop="openDeleteDialog(record)"
                      >
                        <VIcon>ri-delete-bin-line</VIcon>
                      </VBtn>
                    </VCardActions>
                  </VCard>
                </VCol>
              </VRow>

              <div
                v-if="!generating && generatedRecords.length === 0"
                class="text-center text-medium-emphasis py-8"
              >
                <VIcon
                  icon="ri-file-damage-line"
                  size="40"
                  class="mb-2"
                />
                <div>No payroll records generated. Go back and try again.</div>
              </div>
            </div>
        </div>
      </VCard>
    </template>

    <!-- Records mode -->
    <template v-else-if="viewMode === 'records' && !isDetailView">
      <StatCards :cards="recordsStatCards" />

      <VRow
        class="mb-3"
        dense
      >
        <VCol
          cols="12"
          sm="6"
          md="3"
        >
          <VTextField
            v-model="yearMonth"
            label="Month"
            type="month"
            density="compact"
            prepend-inner-icon="ri-calendar-event-line"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="3"
        >
          <VSelect
            v-model="filterStatus"
            :items="statusOptions"
            item-title="title"
            item-value="value"
            label="Status"
            density="compact"
            prepend-inner-icon="ri-filter-3-line"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="3"
        >
          <VSelect
            v-model="filterUnitType"
            :items="[{ title: 'Staff', value: 'staff' }, { title: 'Student', value: 'student' }]"
            item-title="title"
            item-value="value"
            label="Type"
            density="compact"
            prepend-inner-icon="ri-user-line"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="3"
          class="d-flex align-center"
        >
          <VBtn
            variant="tonal"
            color="primary"
            prepend-icon="ri-refresh-line"
            :loading="refreshing"
            @click="refresh"
          >
            Refresh
          </VBtn>
        </VCol>
      </VRow>

      <VProgressLinear
        v-if="loading && !refreshing"
        indeterminate
        color="primary"
        class="mb-2"
      />

      <VCard>
        <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
          <span class="d-flex align-center gap-2">
            <VIcon
              icon="ri-file-list-3-line"
              size="20"
            />
            Monthly payroll records
          </span>
          <span class="text-caption text-medium-emphasis">{{ listCaption || monthLabel }}</span>
        </VCardTitle>
        <div class="payroll-table-scroll">
          <VTable
            class="payroll-table"
            density="compact"
            hover
          >
            <thead>
              <tr>
                <th>Unit</th>
                <th class="text-end">
                  <span class="th-label">
                    <VIcon
                      icon="ri-time-line"
                      size="14"
                    />
                    Regular
                  </span>
                </th>
                <th class="text-end">
                  <span class="th-label">
                    <VIcon
                      icon="ri-grid-line"
                      size="14"
                    />
                    Reg slots
                  </span>
                </th>
                <th class="text-end">
                  <span class="th-label">
                    <VIcon
                      icon="ri-flashlight-line"
                      size="14"
                    />
                    OT
                  </span>
                </th>
                <th class="text-end">
                  <span class="th-label">
                    <VIcon
                      icon="ri-apps-2-line"
                      size="14"
                    />
                    OT slots
                  </span>
                </th>
                <th class="text-end">
                  Base
                </th>
                <th class="text-end">
                  OT Pay
                </th>
                <th class="text-end">
                  Gross
                </th>
                <th class="text-end">
                  Net
                </th>
                <th>Status</th>
                <th class="col-actions" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in records"
                :key="r.id"
                class="payroll-row"
                @click="openDetail(r)"
              >
                <td>
                  <div class="d-flex align-center gap-2">
                    <VAvatar
                      color="primary"
                      variant="tonal"
                      size="28"
                      rounded
                    >
                      <VIcon
                        icon="ri-user-line"
                        size="16"
                      />
                    </VAvatar>
                    <div>
                      <div class="font-weight-medium">
                        {{ r.unit_name || '—' }}
                      </div>
                      <div
                        v-if="r.unit_code"
                        class="text-caption text-medium-emphasis"
                      >
                        {{ r.unit_code }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="text-end">
                  <span class="cell-metric text-success">
                    <VIcon
                      icon="ri-time-line"
                      size="14"
                    />
                    {{ formatHours(r.total_regular_hours) }}
                  </span>
                </td>
                <td class="text-end text-medium-emphasis">
                  <span class="cell-metric">
                    <VIcon
                      icon="ri-grid-line"
                      size="14"
                    />
                    {{ r.regular_slots }}
                  </span>
                </td>
                <td class="text-end">
                  <span class="cell-metric text-info">
                    <VIcon
                      icon="ri-flashlight-line"
                      size="14"
                    />
                    {{ formatHours(r.total_overtime_hours) }}
                  </span>
                </td>
                <td class="text-end text-medium-emphasis">
                  <span class="cell-metric">
                    <VIcon
                      icon="ri-apps-2-line"
                      size="14"
                    />
                    {{ r.ot_slots }}
                  </span>
                </td>
                <td class="text-end">
                  {{ formatCurrency(r.base_salary) }}
                </td>
                <td class="text-end">
                  {{ formatCurrency(r.overtime_pay) }}
                </td>
                <td class="text-end">
                  {{ formatCurrency(r.gross_pay) }}
                </td>
                <td class="text-end font-weight-medium text-primary">
                  {{ formatCurrency(r.net_pay) }}
                </td>
                <td>
                  <VChip
                    :color="statusColorMap[r.status] ?? 'grey'"
                    size="small"
                    label
                    :prepend-icon="statusIcon(r.status)"
                  >
                    {{ r.status }}
                  </VChip>
                </td>
                <td class="col-actions">
                  <div class="d-flex flex-nowrap align-center">
                    <VBtn
                      v-if="r.status === 'draft' || r.status === 'calculated'"
                      size="small"
                      variant="tonal"
                      color="success"
                      prepend-icon="ri-checkbox-circle-line"
                      @click.stop="updateStatus(r, 'approved')"
                    >
                      Approve
                    </VBtn>
                    <VBtn
                      v-if="r.status === 'approved'"
                      size="small"
                      variant="tonal"
                      color="primary"
                      prepend-icon="ri-money-dollar-circle-line"
                      @click.stop="updateStatus(r, 'paid')"
                    >
                      Pay
                    </VBtn>
                    <VBtn
                      v-if="authStore.isSuperAdmin"
                      icon
                      size="small"
                      variant="text"
                      color="error"
                      @click.stop="openDeleteDialog(r)"
                    >
                      <VIcon>ri-delete-bin-line</VIcon>
                    </VBtn>
                  </div>
                </td>
              </tr>
              <tr v-if="records.length === 0 && !loading">
                <td
                  colspan="11"
                  class="text-center text-medium-emphasis py-6"
                >
                  No payroll records found for {{ monthLabel }}. Switch to New run to generate.
                </td>
              </tr>
            </tbody>
          </VTable>
        </div>
        <div class="d-flex align-center justify-space-between pa-3">
          <div class="d-flex align-center gap-2">
            <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
            <VSelect
              v-model="pageSize"
              :items="pageSizeOptions"
              density="compact"
              variant="plain"
              hide-details
              style="max-width: 80px;"
            />
            <span class="text-caption text-medium-emphasis">per page</span>
          </div>
          <VPagination
            v-model="page"
            :length="totalPages"
            :total-visible="5"
            density="compact"
            size="small"
            @update:model-value="loadRecords(true)"
          />
        </div>
      </VCard>
    </template>

    <!-- Detail view -->
    <VCard v-else-if="selectedRecord">
      <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
        <div class="d-flex flex-wrap align-center gap-2">
          <VBtn
            variant="text"
            prepend-icon="ri-arrow-left-line"
            @click="backToOverview"
          >
            Back
          </VBtn>
          <div>
            <div class="font-weight-medium">
              {{ selectedRecord.unit_name || selectedRecord.unit_code }}
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ monthLabel }} · {{ selectedRecord.payroll_period_start }} – {{ selectedRecord.payroll_period_end }}
            </div>
          </div>
        </div>
        <div class="d-flex flex-wrap gap-2">
          <VChip
            :color="statusColorMap[selectedRecord.status] ?? 'grey'"
            label
            :prepend-icon="statusIcon(selectedRecord.status)"
          >
            {{ selectedRecord.status }}
          </VChip>
          <VChip
            color="success"
            label
            prepend-icon="ri-time-line"
          >
            {{ formatHours(selectedRecord.total_regular_hours) }} regular
          </VChip>
          <VChip
            color="info"
            label
            prepend-icon="ri-flashlight-line"
          >
            {{ formatHours(selectedRecord.total_overtime_hours) }} OT
          </VChip>
          <VChip
            color="primary"
            label
            prepend-icon="ri-wallet-3-line"
          >
            Net {{ formatCurrency(selectedRecord.net_pay) }}
          </VChip>
          <VChip
            v-if="detailTotals.autoCheckoutDays > 0"
            color="warning"
            label
            prepend-icon="ri-time-line"
            title="Days closed by day-boundary auto checkout (23:59)"
          >
            {{ detailTotals.autoCheckoutDays }} auto checkout
          </VChip>
        </div>
      </VCardTitle>
      <VCardText class="pb-0">
        <VRow dense>
          <VCol
            cols="12"
            sm="3"
          >
            <div class="text-caption text-medium-emphasis">
              Adjustment 1
            </div>
            <div class="text-h6 font-weight-bold">
              {{ formatCurrency(selectedRecord.adjustment_1) }}
            </div>
            <div class="text-caption text-medium-emphasis mt-1">
              {{ selectedRecord.adjustment_1_remark || '—' }}
            </div>
            <div class="text-caption text-medium-emphasis mt-1">
              Base + OT + Holiday + Adj1 = Gross
            </div>
          </VCol>
          <VCol
            cols="12"
            sm="3"
          >
            <div class="text-caption text-medium-emphasis">
              Gross pay
            </div>
            <div class="text-h6 font-weight-bold">
              {{ formatCurrency(selectedRecord.gross_pay) }}
            </div>
          </VCol>
          <VCol
            cols="12"
            sm="3"
          >
            <div class="text-caption text-medium-emphasis">
              Adjustment 2
            </div>
            <div class="text-h6 font-weight-bold">
              {{ formatCurrency(selectedRecord.adjustment_2) }}
            </div>
            <div class="text-caption text-medium-emphasis mt-1">
              {{ selectedRecord.adjustment_2_remark || '—' }}
            </div>
            <div class="text-caption text-medium-emphasis mt-1">
              Gross + Adj2 = Net
            </div>
          </VCol>
          <VCol
            cols="12"
            sm="3"
          >
            <div class="text-caption text-medium-emphasis">
              Net pay
            </div>
            <div class="text-h6 font-weight-bold text-primary">
              {{ formatCurrency(selectedRecord.net_pay) }}
            </div>
          </VCol>
        </VRow>
      </VCardText>
      <VCardText class="text-caption text-medium-emphasis pb-0">
        Daily attendance summaries used to calculate this payroll record. Edit adjustments on the pay slip card.
      </VCardText>
      <div class="payroll-table-scroll">
        <VTable
          class="payroll-table"
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th>
                <span class="th-label">
                  <VIcon
                    icon="ri-calendar-event-line"
                    size="14"
                  />
                  Date
                </span>
              </th>
              <th>
                <span
                  class="th-label"
                  title="First check-in"
                >
                  <VIcon
                    icon="ri-login-box-line"
                    size="14"
                  />
                  First In
                </span>
              </th>
              <th>
                <span
                  class="th-label"
                  title="Last check-out"
                >
                  <VIcon
                    icon="ri-logout-box-line"
                    size="14"
                  />
                  Last Out
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Regular hours"
                >
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                  />
                  Regular
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Regular 15-min slots"
                >
                  <VIcon
                    icon="ri-grid-line"
                    size="14"
                  />
                  Reg slots
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Overtime hours"
                >
                  <VIcon
                    icon="ri-flashlight-line"
                    size="14"
                  />
                  OT
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Overtime 15-min slots"
                >
                  <VIcon
                    icon="ri-apps-2-line"
                    size="14"
                  />
                  OT slots
                </span>
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in summaries"
              :key="s.id"
            >
              <td>
                <SummaryDateCell :date="s.summary_date" />
              </td>
              <td>
                <span
                  v-if="s.first_check_in"
                  class="cell-metric"
                  title="First check-in"
                >
                  <VIcon
                    icon="ri-login-box-line"
                    size="14"
                    class="text-success"
                  />
                  <span class="text-caption">{{ formatAttendanceDateTime(s.first_check_in) }}</span>
                </span>
                <span
                  v-else
                  class="text-medium-emphasis"
                >—</span>
              </td>
              <td>
                <span
                  v-if="s.last_check_out"
                  class="cell-metric"
                  title="Last check-out"
                >
                  <VIcon
                    icon="ri-logout-box-line"
                    size="14"
                    class="text-info"
                  />
                  <span class="text-caption">{{ formatAttendanceDateTime(s.last_check_out) }}</span>
                </span>
                <span
                  v-else
                  class="text-medium-emphasis"
                >—</span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Regular hours"
                >
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                    class="text-success"
                  />
                  {{ formatHours(s.regular_hours) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric text-medium-emphasis"
                  title="Regular 15-min slots"
                >
                  <VIcon
                    icon="ri-grid-line"
                    size="14"
                  />
                  {{ s.regular_slots }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Overtime hours"
                >
                  <VIcon
                    icon="ri-flashlight-line"
                    size="14"
                    class="text-info"
                  />
                  {{ formatHours(s.overtime_hours) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric text-medium-emphasis"
                  title="Overtime 15-min slots"
                >
                  <VIcon
                    icon="ri-apps-2-line"
                    size="14"
                  />
                  {{ s.ot_slots }}
                </span>
              </td>
              <td>
                <div class="d-flex flex-wrap align-center gap-1">
                  <VChip
                    :color="statusColor(s)"
                    size="small"
                    label
                    :prepend-icon="summaryStatusIcon(s)"
                  >
                    {{ statusLabel(s) }}
                  </VChip>
                  <AutoCheckoutChip
                    :notes="s.attendance_notes"
                    :last-check-out="s.last_check_out"
                  />
                </div>
              </td>
            </tr>
            <tr
              v-if="summaries.length > 0"
              class="font-weight-bold"
            >
              <td>Total</td>
              <td />
              <td />
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Regular hours total"
                >
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                    class="text-success"
                  />
                  {{ formatHours(detailTotals.regular) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric text-medium-emphasis"
                  title="Regular slots total"
                >
                  <VIcon
                    icon="ri-grid-line"
                    size="14"
                  />
                  {{ detailTotals.regularSlots }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Overtime hours total"
                >
                  <VIcon
                    icon="ri-flashlight-line"
                    size="14"
                    class="text-info"
                  />
                  {{ formatHours(detailTotals.overtime) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric text-medium-emphasis"
                  title="Overtime slots total"
                >
                  <VIcon
                    icon="ri-apps-2-line"
                    size="14"
                  />
                  {{ detailTotals.otSlots }}
                </span>
              </td>
              <td />
            </tr>
            <tr v-if="summaries.length === 0 && !loading">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                No daily summaries found for this unit in {{ monthLabel }}.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div class="text-caption text-medium-emphasis pa-3">
        {{ detailTotals.days }} day{{ detailTotals.days === 1 ? '' : 's' }} · {{ detailTotalCount }} records loaded for this month
      </div>
    </VCard>

    <!-- Delete dialog -->
    <VDialog
      v-model="deleteDialog"
      max-width="400"
    >
      <VCard v-if="deleteTarget">
        <VCardTitle class="text-h6">
          Confirm Delete
        </VCardTitle>
        <VCardText>
          Delete payroll record for <strong>{{ deleteTarget.unit_name || deleteTarget.unit_code || deleteTarget.unit_id }}</strong> ({{ deleteTarget.payroll_period_start }} – {{ deleteTarget.payroll_period_end }})?
        </VCardText>
        <VCardActions class="justify-end">
          <VBtn
            variant="text"
            @click="closeDeleteDialog"
          >
            Cancel
          </VBtn>
          <VBtn
            color="error"
            variant="flat"
            @click="confirmDelete"
          >
            Delete
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.payroll-wizard {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.payroll-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
}

.payroll-steps-arrow {
  flex-shrink: 0;
}

.payroll-step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  cursor: pointer;
  font: inherit;
  font-weight: 500;
  padding: 8px 12px;
  transition: background-color 0.15s ease, color 0.15s ease;

  &:hover {
    background: rgba(var(--v-theme-on-surface), 0.04);
  }
}

.payroll-step--active {
  background: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
}

.type-card {
  transition: transform 0.15s ease;

  &:hover {
    transform: translateY(-2px);
  }
}

.unit-list {
  max-block-size: 340px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}

.unit-list-item {
  cursor: pointer;
}

.payroll-invoice {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.invoice-header {
  padding-block: 16px;
}

.invoice-body {
  padding-block: 16px;
}

.invoice-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.invoice-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.invoice-line {
  display: flex;
  justify-content: space-between;
  padding-block: 4px;
}

.invoice-adj-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-block: 6px;
}

.invoice-remark {
  flex: 1 1 auto;
  min-inline-size: 0;
}

.invoice-adj-amount {
  flex: 0 0 112px;
  max-inline-size: 112px;
}

.invoice-adj-amount :deep(input) {
  text-align: end;
}

.invoice-line.total {
  border-top: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
  margin-top: 4px;
  padding-top: 8px;
}

.invoice-line.grand {
  margin-top: 4px;
}

.payroll-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.payroll-table :deep(th),
.payroll-table :deep(td) {
  white-space: nowrap;
}

.payroll-table :deep(.col-actions) {
  width: 1%;
  white-space: nowrap;
  vertical-align: middle;
}

.payroll-row {
  cursor: pointer;
}

.th-label,
.cell-metric {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.text-end .th-label,
.text-end .cell-metric {
  justify-content: flex-end;
}
</style>
