<script setup lang="ts">
import { deletePayrollRecord, generatePayroll, getPayrollStats, listPayrollRecordsWithTotal, updatePayrollRecord } from '@/api/attendance/payroll'
import type { PayrollRecord, PayrollStats } from '@/api/attendance/payroll'
import { listSummariesWithTotal, listSummaryOverview } from '@/api/attendance/summaries'
import type { AttendanceSummary } from '@/api/attendance/summaries'
import { listUnits } from '@/api/attendance/units'
import type { Unit } from '@/api/attendance/units'
import AutoCheckoutChip from '@/components/attendance/AutoCheckoutChip.vue'
import PayrollGenerateTab from '@/components/attendance/payroll/PayrollGenerateTab.vue'
import PayrollHistoryTab from '@/components/attendance/payroll/PayrollHistoryTab.vue'
import PayrollReviewTab from '@/components/attendance/payroll/PayrollReviewTab.vue'
import SummaryDateCell from '@/components/attendance/SummaryDateCell.vue'
import { formatAttendanceDateTime, isAutoCheckoutSummaryDay } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { formatPayrollGenerateMessage } from '@/utils/formatGenerateResult'
import {
  canApprovePayroll,
  canEditPayrollAdjustments,
  canPayPayroll,
  formatPayrollCurrency,
  formatPayrollHours,
  payrollStatusColorMap,
  payrollStatusIcon,
  safePayrollNumber,
} from '@/utils/payrollDisplay'

definePage({ meta: {} })

const { authStore, ensureAccess } = useAttendanceAdminGate()

const {
  yearMonth,
  parsed: parsedYearMonth,
  monthDateRange,
  monthLabel,
  changeMonth,
  toCurrentMonth,
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
const historyUnitType = ref('staff')
const historySearch = ref('')
const generating = ref(false)
const generateError = ref('')
const generateSuccess = ref<{ title: string; detail?: string; warning?: string } | null>(null)
const deleteDialog = ref(false)
const deleteTarget = ref<PayrollRecord | null>(null)
const approveDialog = ref(false)
const approveTarget = ref<PayrollRecord | null>(null)
const approving = ref(false)
const payDialog = ref(false)
const payTarget = ref<PayrollRecord | null>(null)
const paying = ref(false)

const selectedRecord = ref<PayrollRecord | null>(null)
const summaries = ref<AttendanceSummary[]>([])
const detailTotalCount = ref(0)

const viewMode = ref<'generate' | 'review' | 'history'>('review')
const reviewSlips = ref<PayrollRecord[]>([])
const reviewLoading = ref(false)
const reviewError = ref('')
const reviewSearch = ref('')
const reviewStatus = ref('')

const generateUnits = ref<Unit[]>([])
const generateUnitsLoading = ref(false)
const generateUnitsError = ref('')
const generateSelectedIds = ref<string[]>([])
const generateSearch = ref('')

/** Default: only staff who have attendance summaries for the payroll month. */
const generateShowAllStaff = ref(false)
const generateStaffWithSummariesCount = ref(0)

const isDetailView = computed(() => !!selectedRecord.value)

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  return pagedListCaption(records.value.length)
})

const detailTotals = computed(() => {
  const regular = summaries.value.reduce((sum, s) => sum + safePayrollNumber(s.regular_hours), 0)
  const regularSlots = summaries.value.reduce((sum, s) => sum + safePayrollNumber(s.regular_slots), 0)
  const overtime = summaries.value.reduce((sum, s) => sum + safePayrollNumber(s.overtime_hours), 0)
  const otSlots = summaries.value.reduce((sum, s) => sum + safePayrollNumber(s.ot_slots), 0)
  const autoCheckoutDays = summaries.value.filter(s => isAutoCheckoutSummaryDay(s)).length

  return { regular, regularSlots, overtime, otSlots, days: summaries.value.length, autoCheckoutDays }
})

const generateSelectedCount = computed(() => generateSelectedIds.value.length)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value && viewMode.value !== 'generate')
    return 'Loading…'

  if (isDetailView.value && selectedRecord.value)
    return `${selectedRecord.value.unit_name || selectedRecord.value.unit_code} · ${monthLabel.value}`

  if (viewMode.value === 'generate')
    return `${monthLabel.value} · ${generateSelectedCount.value} of ${generateUnits.value.length} staff selected`

  if (viewMode.value === 'review')
    return `${monthLabel.value} · review and approve slips`

  return `${monthLabel.value} · lookup paid and past slips`
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return

  toCurrentMonth()
  await loadRecords()
  await loadReviewSlips()
})

watch(yearMonth, () => {
  selectedRecord.value = null
  summaries.value = []
  loadRecords(true, true)
  if (viewMode.value === 'review')
    loadReviewSlips(true)
  if (viewMode.value === 'generate')
    loadGenerateUnits()
})

watch([filterStatus, historyUnitType], () => {
  selectedRecord.value = null
  summaries.value = []
  if (viewMode.value === 'history')
    loadRecords(true, true)
})

watch(pageSize, () => {
  resetPage()
  loadRecords(true)
})

useAutoClearAlerts(generateSuccess, generateError, loadError, reviewError)

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
        unit_type: historyUnitType.value || undefined,
        year: parsed.year,
        month: parsed.month,
        page: page.value,
        page_size: pageSize.value,
      }),
      getPayrollStats({
        status: filterStatus.value || undefined,
        unit_type: historyUnitType.value || undefined,
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
  if (!canEditPayrollAdjustments(record))
    return

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

function backToOverview() {
  selectedRecord.value = null
  summaries.value = []
}

function refresh() {
  if (selectedRecord.value) {
    loadDetail(true)

    return
  }
  if (viewMode.value === 'review')
    loadReviewSlips(true)
  else if (viewMode.value === 'generate')
    loadGenerateUnits()
  else
    loadRecords(true)
}

async function updateStatus(record: PayrollRecord, newStatus: string) {
  try {
    await updatePayrollRecord(record.id, { status: newStatus })
    record.status = newStatus as PayrollRecord['status']

    return true
  }
  catch (e) {
    console.error('Failed to update status', e)
    loadError.value = formatApiError(e, 'Could not update status')

    return false
  }
}

function openApproveDialog(record: PayrollRecord) {
  approveTarget.value = record
  approveDialog.value = true
}

function closeApproveDialog() {
  approveDialog.value = false
  approveTarget.value = null
}

async function confirmApprove() {
  if (!approveTarget.value)
    return

  approving.value = true
  try {
    const ok = await updateStatus(approveTarget.value, 'approved')
    if (ok)
      closeApproveDialog()
  }
  finally {
    approving.value = false
  }
}

function openPayDialog(record: PayrollRecord) {
  payTarget.value = record
  payDialog.value = true
}

function closePayDialog() {
  payDialog.value = false
  payTarget.value = null
}

async function confirmPay() {
  if (!payTarget.value)
    return

  paying.value = true
  try {
    const ok = await updateStatus(payTarget.value, 'paid')
    if (ok)
      closePayDialog()
  }
  finally {
    paying.value = false
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
    await Promise.all([
      loadRecords(true),
      viewMode.value === 'review' ? loadReviewSlips(true) : Promise.resolve(),
    ])
  }
  catch (e) {
    console.error('Failed to delete record', e)
    loadError.value = formatApiError(e, 'Could not delete record')
  }
}

function showGenerate() {
  viewMode.value = 'generate'
  selectedRecord.value = null
  summaries.value = []
  generateError.value = ''
  loadGenerateUnits()
}

function showReview() {
  viewMode.value = 'review'
  selectedRecord.value = null
  summaries.value = []
  loadReviewSlips()
}

function showHistory() {
  viewMode.value = 'history'
  selectedRecord.value = null
  summaries.value = []
  loadRecords(true, true)
}

function onViewModeChange(mode: 'generate' | 'review' | 'history' | null) {
  if (mode === 'generate')
    showGenerate()
  else if (mode === 'history')
    showHistory()
  else if (mode === 'review')
    showReview()
}

function onHistoryPageChange(value: number) {
  page.value = value
  loadRecords(true)
}

async function loadReviewSlips(isRefresh = false) {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return

  if (isRefresh)
    refreshing.value = true
  else
    reviewLoading.value = true
  reviewError.value = ''
  try {
    const result = await listPayrollRecordsWithTotal({
      unit_type: 'staff',
      year: parsed.year,
      month: parsed.month,
      page: 1,
      page_size: 200,
    })

    reviewSlips.value = result.items
  }
  catch (e) {
    console.error('Failed to load payroll slips for review', e)
    reviewError.value = formatApiError(e, 'Failed to load payroll slips. Please try again.')
  }
  finally {
    reviewLoading.value = false
    refreshing.value = false
  }
}

async function loadGenerateUnits() {
  generateUnitsLoading.value = true
  generateUnitsError.value = ''
  try {
    const range = monthDateRange.value
    if (!range) {
      generateUnits.value = []
      generateSelectedIds.value = []
      generateStaffWithSummariesCount.value = 0
      generateUnitsError.value = 'Select a valid month'

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

    generateStaffWithSummariesCount.value = withSummaryIds.size

    const sorted = [...allStaff].sort((a, b) => a.full_name.localeCompare(b.full_name))

    generateUnits.value = generateShowAllStaff.value
      ? sorted
      : sorted.filter(u => withSummaryIds.has(u.id))

    // Keep prior selection when possible; otherwise select everyone in the visible list
    const visibleIds = new Set(generateUnits.value.map(u => u.id))
    const kept = generateSelectedIds.value.filter(id => visibleIds.has(id))

    generateSelectedIds.value = kept.length > 0
      ? kept
      : generateUnits.value.map(u => u.id)
  }
  catch (e) {
    console.error('Failed to load units for payroll generation', e)
    generateUnitsError.value = formatApiError(e, 'Failed to load units')
  }
  finally {
    generateUnitsLoading.value = false
  }
}

watch(generateShowAllStaff, () => {
  if (viewMode.value === 'generate')
    loadGenerateUnits()
})

async function handleGenerate() {
  const parsed = parsedYearMonth.value
  if (!parsed) {
    generateError.value = 'Select a valid month'

    return
  }
  if (generateSelectedCount.value === 0) {
    generateError.value = 'Select at least one staff member'

    return
  }

  const { year, month } = parsed

  const allSelected = generateUnits.value.length > 0
    && generateSelectedIds.value.length === generateUnits.value.length

  const idsToSend = allSelected ? undefined : generateSelectedIds.value

  generating.value = true
  generateError.value = ''
  generateSuccess.value = null
  try {
    const generateResult = await generatePayroll(year, month, 'staff', idsToSend)

    const generateMessage = formatPayrollGenerateMessage(generateResult, year, month)
    const reviewHint = 'Edit adjustments and approve on Review.'

    generateSuccess.value = {
      ...generateMessage,
      detail: generateMessage.detail ? `${generateMessage.detail} ${reviewHint}` : reviewHint,
    }
    historyUnitType.value = 'staff'
    reviewStatus.value = ''
    reviewSearch.value = ''
    await Promise.all([
      loadReviewSlips(),
      loadRecords(true, true),
    ])
    viewMode.value = 'review'
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
</script>

<template>
  <VContainer>
    <!-- Header -->
    <VRow
      class="mb-4"
      align="center"
    >
      <VCol>
        <div class="d-flex align-center gap-2">
          <VBtn
            v-if="isDetailView"
            variant="text"
            prepend-icon="ri-arrow-left-line"
            @click="backToOverview"
          >
            Back
          </VBtn>
          <h1 class="text-h5 font-weight-bold mb-0">
            Payroll
          </h1>
        </div>
        <p class="text-subtitle-2 text-medium-emphasis mb-0">
          {{ pageSubtitle }}
        </p>
      </VCol>
      <VCol
        cols="12"
        md="auto"
        class="d-flex flex-wrap align-center gap-2 justify-md-end"
      >
        <VBtn
          icon
          variant="tonal"
          size="small"
          @click="changeMonth(-1)"
        >
          <VIcon>ri-arrow-left-s-line</VIcon>
        </VBtn>
        <VTextField
          v-model="yearMonth"
          label="Month"
          type="month"
          density="compact"
          hide-details
          class="month-field"
        />
        <VBtn
          icon
          variant="tonal"
          size="small"
          @click="changeMonth(1)"
        >
          <VIcon>ri-arrow-right-s-line</VIcon>
        </VBtn>
      </VCol>
    </VRow>

    <VTabs
      v-if="!isDetailView"
      :model-value="viewMode"
      color="primary"
      class="mb-4"
      @update:model-value="onViewModeChange"
    >
      <VTab value="review">
        <VIcon
          start
          icon="ri-file-paper-2-line"
        />
        Review
      </VTab>
      <VTab value="generate">
        <VIcon
          start
          icon="ri-magic-line"
        />
        Generate
      </VTab>
      <VTab value="history">
        <VIcon
          start
          icon="ri-list-check-2"
        />
        History
      </VTab>
    </VTabs>

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

    <PayrollReviewTab
      v-if="viewMode === 'review' && !isDetailView"
      :month-label="monthLabel"
      :slips="reviewSlips"
      :loading="reviewLoading"
      :refreshing="refreshing"
      :error="reviewError"
      :search="reviewSearch"
      :status="reviewStatus"
      :can-delete="authStore.isSuperAdmin"
      @update:search="reviewSearch = $event"
      @update:status="reviewStatus = $event"
      @refresh="refresh"
      @generate="showGenerate"
      @approve="openApproveDialog"
      @pay="openPayDialog"
      @detail="openDetail"
      @delete="openDeleteDialog"
      @adj-change="onCardAdjChange"
    />

    <PayrollGenerateTab
      v-else-if="viewMode === 'generate' && !isDetailView"
      :month-label="monthLabel"
      :units="generateUnits"
      :units-loading="generateUnitsLoading"
      :units-error="generateUnitsError"
      :selected-ids="generateSelectedIds"
      :search="generateSearch"
      :show-all-staff="generateShowAllStaff"
      :staff-with-summaries-count="generateStaffWithSummariesCount"
      :generating="generating"
      :generate-error="generateError"
      @update:search="generateSearch = $event"
      @update:show-all-staff="generateShowAllStaff = $event"
      @update:selected-ids="generateSelectedIds = $event"
      @generate="handleGenerate"
    />

    <PayrollHistoryTab
      v-else-if="viewMode === 'history' && !isDetailView"
      :month-label="monthLabel"
      :records="records"
      :stats="payrollStats"
      :loading="loading"
      :refreshing="refreshing"
      :search="historySearch"
      :filter-status="filterStatus"
      :unit-type="historyUnitType"
      :page="page"
      :page-size="pageSize"
      :page-size-options="pageSizeOptions"
      :total-count="totalCount"
      :total-pages="totalPages"
      :list-caption="listCaption"
      :can-delete="authStore.isSuperAdmin"
      @update:search="historySearch = $event"
      @update:filter-status="filterStatus = $event"
      @update:unit-type="historyUnitType = $event"
      @update:page="onHistoryPageChange"
      @update:page-size="pageSize = $event"
      @refresh="refresh"
      @review="showReview"
      @generate="showGenerate"
      @detail="openDetail"
      @delete="openDeleteDialog"
    />

    <!-- Detail view -->
    <VCard v-else-if="selectedRecord">
      <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
        <div>
          <div class="font-weight-medium">
            {{ selectedRecord.unit_name || selectedRecord.unit_code }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ monthLabel }} · {{ selectedRecord.payroll_period_start }} – {{ selectedRecord.payroll_period_end }}
          </div>
        </div>
        <div class="d-flex flex-wrap gap-2">
          <VChip
            :color="payrollStatusColorMap[selectedRecord.status] ?? 'grey'"
            label
            :prepend-icon="payrollStatusIcon(selectedRecord.status)"
          >
            {{ selectedRecord.status }}
          </VChip>
          <VChip
            color="success"
            label
            prepend-icon="ri-time-line"
          >
            {{ formatPayrollHours(selectedRecord.total_regular_hours) }} regular
          </VChip>
          <VChip
            color="info"
            label
            prepend-icon="ri-flashlight-line"
          >
            {{ formatPayrollHours(selectedRecord.total_overtime_hours) }} OT
          </VChip>
          <VChip
            color="primary"
            label
            prepend-icon="ri-wallet-3-line"
          >
            Net {{ formatPayrollCurrency(selectedRecord.net_pay) }}
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
          <VBtn
            v-if="canApprovePayroll(selectedRecord)"
            size="small"
            variant="tonal"
            color="success"
            prepend-icon="ri-checkbox-circle-line"
            @click="openApproveDialog(selectedRecord)"
          >
            Approve
          </VBtn>
          <VBtn
            v-if="canPayPayroll(selectedRecord)"
            size="small"
            variant="tonal"
            color="primary"
            prepend-icon="ri-money-dollar-circle-line"
            @click="openPayDialog(selectedRecord)"
          >
            Pay
          </VBtn>
        </div>
      </VCardTitle>
      <VCardText class="pb-0">
        <VRow dense>
          <VCol
            cols="12"
            sm="2"
          >
            <div class="text-caption text-medium-emphasis">
              Base
            </div>
            <div class="text-h6 font-weight-bold">
              {{ formatPayrollCurrency(selectedRecord.base_salary) }}
            </div>
            <div class="text-caption text-medium-emphasis mt-1">
              OT {{ formatPayrollCurrency(selectedRecord.overtime_pay) }}
              · Holiday {{ formatPayrollCurrency(selectedRecord.holiday_pay) }}
            </div>
          </VCol>
          <VCol
            cols="12"
            sm="2"
          >
            <div class="text-caption text-medium-emphasis">
              Adjustment 1
            </div>
            <div class="text-h6 font-weight-bold">
              {{ formatPayrollCurrency(selectedRecord.adjustment_1) }}
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
            sm="2"
          >
            <div class="text-caption text-medium-emphasis">
              Gross pay
            </div>
            <div class="text-h6 font-weight-bold">
              {{ formatPayrollCurrency(selectedRecord.gross_pay) }}
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
              {{ formatPayrollCurrency(selectedRecord.adjustment_2) }}
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
              {{ formatPayrollCurrency(selectedRecord.net_pay) }}
            </div>
          </VCol>
        </VRow>
      </VCardText>
      <VCardText class="text-caption text-medium-emphasis pb-0">
        Daily attendance summaries used to calculate this payroll record. Adjustments can be edited on calculated slips only.
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
                  {{ formatPayrollHours(s.regular_hours) }}
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
                  {{ formatPayrollHours(s.overtime_hours) }}
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
                  {{ formatPayrollHours(detailTotals.regular) }}
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
                  {{ formatPayrollHours(detailTotals.overtime) }}
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

    <AttendanceConfirmDialog
      v-model="approveDialog"
      title="Approve payroll slip?"
      confirm-label="Approve"
      confirm-color="success"
      :loading="approving"
      @confirm="confirmApprove"
      @cancel="closeApproveDialog"
    >
      <template v-if="approveTarget">
        Approve payroll for
        <strong>{{ approveTarget.unit_name || approveTarget.unit_code || approveTarget.unit_id }}</strong>
        ({{ approveTarget.payroll_period_start }} – {{ approveTarget.payroll_period_end }})?
        Adjustments will be locked after approval. Net pay
        <strong>{{ formatPayrollCurrency(approveTarget.net_pay) }}</strong>.
      </template>
    </AttendanceConfirmDialog>

    <AttendanceConfirmDialog
      v-model="payDialog"
      title="Mark payroll as paid?"
      confirm-label="Pay"
      confirm-color="primary"
      :loading="paying"
      @confirm="confirmPay"
      @cancel="closePayDialog"
    >
      <template v-if="payTarget">
        Mark payroll as paid for
        <strong>{{ payTarget.unit_name || payTarget.unit_code || payTarget.unit_id }}</strong>
        ({{ payTarget.payroll_period_start }} – {{ payTarget.payroll_period_end }})?
        Net pay
        <strong>{{ formatPayrollCurrency(payTarget.net_pay) }}</strong>.
        This should only be done after payment is complete.
      </template>
    </AttendanceConfirmDialog>

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
.month-field {
  inline-size: 160px;
}

.payroll-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.payroll-table :deep(th),
.payroll-table :deep(td) {
  white-space: nowrap;
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
