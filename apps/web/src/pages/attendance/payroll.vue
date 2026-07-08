<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { deletePayrollRecord, generatePayroll, listPayrollRecordsWithTotal, updatePayrollRecord } from '@/api/attendance/payroll'
import type { PayrollRecord } from '@/api/attendance/payroll'
import { listSummariesWithTotal } from '@/api/attendance/summaries'
import type { AttendanceSummary } from '@/api/attendance/summaries'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatPayrollGenerateMessage } from '@/utils/formatGenerateResult'

definePage({ meta: {} })

const DETAIL_PAGE_SIZE = 100
const pageSize = ref(40)
const pageSizeOptions = [10, 20, 40, 60, 100]

const authStore = useAttendanceAuthStore()
const router = useRouter()

const records = ref<PayrollRecord[]>([])
const totalCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filterStatus = ref('')
const filterProductType = ref('staff')
const yearMonth = ref('')
const generating = ref(false)
const generateError = ref('')
const generateSuccess = ref<{ title: string; detail?: string } | null>(null)
const page = ref(1)
const deleteDialog = ref(false)
const deleteTarget = ref<PayrollRecord | null>(null)

const selectedRecord = ref<PayrollRecord | null>(null)
const summaries = ref<AttendanceSummary[]>([])
const detailTotalCount = ref(0)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

const isDetailView = computed(() => !!selectedRecord.value)

const typeOptions = [
  { title: 'All types', value: '' },
  { title: 'Staff', value: 'staff' },
  { title: 'Student', value: 'student' },
]

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

const parsedYearMonth = computed(() => {
  const ym = yearMonth.value
  if (!ym || !/^\d{4}-\d{2}$/.test(ym))
    return null

  const [year, month] = ym.split('-').map(Number)

  return { year, month }
})

const monthDateRange = computed(() => {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return null

  const { year, month } = parsed
  const end = new Date(year, month, 0)
  const pad = (n: number) => String(n).padStart(2, '0')

  return {
    date_from: `${year}-${pad(month)}-01`,
    date_to: `${year}-${pad(month)}-${pad(end.getDate())}`,
  }
})

const monthLabel = computed(() => {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return 'Select a month'

  return new Date(parsed.year, parsed.month - 1, 1).toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
})

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  if (isDetailView.value && selectedRecord.value)
    return `${selectedRecord.value.product_name || selectedRecord.value.product_code} · ${monthLabel.value}`

  const selectedTypeLabel = typeOptions.find(o => o.value === filterProductType.value)?.title ?? 'All types'

  return `${monthLabel.value} · ${selectedTypeLabel} · ${totalCount.value} record${totalCount.value === 1 ? '' : 's'}`
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * pageSize.value + 1
  const to = from + records.value.length - 1

  if (totalCount.value <= pageSize.value)
    return `${totalCount.value} record${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

const statCards = computed(() => {
  const count = records.value.length
  const regular = records.value.reduce((sum, r) => sum + safeNumber(r.total_regular_hours), 0)
  const overtime = records.value.reduce((sum, r) => sum + safeNumber(r.total_overtime_hours), 0)
  const net = records.value.reduce((sum, r) => sum + safeNumber(r.net_pay), 0)

  return [
    { label: 'Records', value: String(count), hint: 'products this page' },
    { label: 'Regular hours', value: formatHours(regular), hint: 'sum of this page' },
    { label: 'OT hours', value: formatHours(overtime), hint: 'sum of this page' },
    { label: 'Net pay', value: formatCurrency(net), hint: 'sum of this page' },
  ]
})

const detailTotals = computed(() => {
  const regular = summaries.value.reduce((sum, s) => sum + safeNumber(s.regular_hours), 0)
  const regularSlots = summaries.value.reduce((sum, s) => sum + safeNumber(s.regular_slots), 0)
  const overtime = summaries.value.reduce((sum, s) => sum + safeNumber(s.overtime_hours), 0)
  const otSlots = summaries.value.reduce((sum, s) => sum + safeNumber(s.ot_slots), 0)
  const breakMinutes = summaries.value.reduce((sum, s) => sum + safeNumber(s.total_break_minutes), 0)

  return { regular, regularSlots, overtime, otSlots, breakMinutes, days: summaries.value.length }
})

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (!authStore.isAdmin) {
    router.replace({ name: 'attendance-dashboard' })

    return
  }
  const now = new Date()

  yearMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  await loadRecords()
})

watch([yearMonth, filterProductType], () => {
  selectedRecord.value = null
  summaries.value = []
  loadRecords(true, true)
})

watch(filterStatus, () => {
  loadRecords(true, true)
})

async function loadRecords(isRefresh = false, resetPage = false) {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return

  if (resetPage)
    page.value = 1
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listPayrollRecordsWithTotal({
      status: filterStatus.value || undefined,
      product_type: filterProductType.value || undefined,
      year: parsed.year,
      month: parsed.month,
      page: page.value,
      page_size: pageSize.value,
    })

    records.value = result.items
    totalCount.value = result.total
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
      product_id: selectedRecord.value.product_id,
      date_from: range.date_from,
      date_to: range.date_to,
      page: 1,
      page_size: DETAIL_PAGE_SIZE,
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

function changeMonth(delta: number) {
  const parsed = parsedYearMonth.value
  if (!parsed)
    return

  const next = new Date(parsed.year, parsed.month - 1 + delta, 1)

  yearMonth.value = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
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

function onPageSizeChange() {
  page.value = 1
  loadRecords(true)
}

async function handleGenerate() {
  const parsed = parsedYearMonth.value
  if (!parsed) {
    generateError.value = 'Select a valid year-month (YYYY-MM)'

    return
  }

  const { year, month } = parsed

  generating.value = true
  generateError.value = ''
  generateSuccess.value = null
  try {
    const result = await generatePayroll(year, month)

    generateSuccess.value = formatPayrollGenerateMessage(result, year, month)
    await loadRecords(true)
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

function formatHours(h: number) {
  return Number.isFinite(h) ? h.toFixed(2) : '-'
}

function minutesToHours(m: number) {
  return Number.isFinite(m) ? (m / 60).toFixed(2) : '-'
}

function safeNumber(value: number) {
  return Number.isFinite(value) ? value : 0
}

function formatCurrency(n: number) {
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <h1 class="text-h5 font-weight-bold">
          Payroll Records
        </h1>
        <p class="text-subtitle-2 text-medium-emphasis">
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
        <VSelect
          v-model="filterProductType"
          :items="typeOptions"
          label="Type"
          density="compact"
          hide-details
          class="type-field"
        />
        <VSelect
          v-model="filterStatus"
          :items="statusOptions"
          item-title="title"
          item-value="value"
          label="Status"
          density="compact"
          hide-details
          class="status-field"
        />
        <VBtn
          color="primary"
          :loading="generating"
          prepend-icon="ri-magic-line"
          title="Build or refresh payroll records from attendance summaries for this month"
          @click="handleGenerate"
        >
          Generate
        </VBtn>
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

    <VAlert
      v-if="generateError"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ generateError }}
    </VAlert>
    <VAlert
      v-if="generateSuccess"
      type="success"
      variant="tonal"
      density="compact"
      class="mb-3"
      closable
      :title="generateSuccess.title"
      :text="generateSuccess.detail"
      @click:close="generateSuccess = null"
    />

    <VRow
      v-if="!isDetailView"
      class="mb-3"
      dense
    >
      <VCol
        v-for="card in statCards"
        :key="card.label"
        cols="12"
        sm="6"
        md="3"
      >
        <VCard class="pa-3">
          <div class="text-caption text-medium-emphasis">
            {{ card.label }}
          </div>
          <div class="text-h6 font-weight-bold">
            {{ card.value }}
          </div>
          <div class="text-caption text-medium-emphasis">
            {{ card.hint }}
          </div>
        </VCard>
      </VCol>
    </VRow>

    <VProgressLinear
      v-if="loading && !refreshing"
      indeterminate
      color="primary"
      class="mb-2"
    />

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ loadError }}
    </VAlert>

    <VCard v-if="!isDetailView">
      <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
        <span>Monthly payroll</span>
        <span class="text-caption text-medium-emphasis">
          {{ listCaption || monthLabel }}
        </span>
      </VCardTitle>
      <div class="payroll-table-scroll">
        <VTable
          class="payroll-table"
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th>
                Product
              </th>
              <th class="text-end">
                Regular
              </th>
              <th class="text-end">
                Reg slots
              </th>
              <th class="text-end">
                OT
              </th>
              <th class="text-end">
                OT slots
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
              <th>
                Status
              </th>
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
                <div class="font-weight-medium">
                  {{ r.product_name || '—' }}
                </div>
                <div
                  v-if="r.product_code"
                  class="text-caption text-medium-emphasis"
                >
                  {{ r.product_code }}
                </div>
              </td>
              <td class="text-end">
                {{ formatHours(r.total_regular_hours) }}
              </td>
              <td class="text-end text-medium-emphasis">
                {{ r.regular_slots }}
              </td>
              <td class="text-end">
                {{ formatHours(r.total_overtime_hours) }}
              </td>
              <td class="text-end text-medium-emphasis">
                {{ r.ot_slots }}
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
              <td class="text-end">
                {{ formatCurrency(r.net_pay) }}
              </td>
              <td>
                <VChip
                  :color="statusColorMap[r.status] ?? 'grey'"
                  size="small"
                  label
                >
                  {{ r.status }}
                </VChip>
              </td>
              <td class="col-actions">
                <div class="d-flex flex-nowrap align-center">
                  <VBtn
                    v-if="r.status === 'draft' || r.status === 'calculated'"
                    size="small"
                    variant="text"
                    color="success"
                    @click.stop="updateStatus(r, 'approved')"
                  >
                    Approve
                  </VBtn>
                  <VBtn
                    v-if="r.status === 'approved'"
                    size="small"
                    variant="text"
                    color="primary"
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
                No payroll records found for {{ monthLabel }}. Click Generate to build them from attendance summaries.
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
            @update:model-value="onPageSizeChange"
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

    <VCard v-else-if="selectedRecord">
      <VCardTitle class="d-flex flex-wrap align-center justify-space-between gap-2">
        <div class="d-flex flex-wrap align-center gap-2">
          <VBtn
            variant="text"
            prepend-icon="ri-arrow-left-line"
            @click="backToOverview"
          >
            Back to overview
          </VBtn>
          <div>
            <div class="font-weight-medium">
              {{ selectedRecord.product_name || selectedRecord.product_code }}
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
          >
            {{ selectedRecord.status }}
          </VChip>
          <VChip
            color="success"
            label
          >
            {{ formatHours(selectedRecord.total_regular_hours) }} regular
          </VChip>
          <VChip
            color="info"
            label
          >
            {{ formatHours(selectedRecord.total_overtime_hours) }} OT
          </VChip>
          <VChip
            color="primary"
            label
          >
            Net {{ formatCurrency(selectedRecord.net_pay) }}
          </VChip>
        </div>
      </VCardTitle>
      <VCardText class="text-caption text-medium-emphasis pb-0">
        Daily attendance summaries used to calculate this payroll record.
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
                Date
              </th>
              <th>
                First In
              </th>
              <th>
                Last Out
              </th>
              <th class="text-end">
                Regular
              </th>
              <th class="text-end">
                Reg slots
              </th>
              <th class="text-end">
                OT
              </th>
              <th class="text-end">
                OT slots
              </th>
              <th class="text-end">
                Break
              </th>
              <th>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in summaries"
              :key="s.id"
            >
              <td>{{ s.summary_date }}</td>
              <td>
                <span
                  v-if="s.first_check_in"
                  class="text-caption"
                >{{ s.first_check_in.slice(0, 16).replace('T', ' ') }}</span>
                <span
                  v-else
                  class="text-medium-emphasis"
                >—</span>
              </td>
              <td>
                <span
                  v-if="s.last_check_out"
                  class="text-caption"
                >{{ s.last_check_out.slice(0, 16).replace('T', ' ') }}</span>
                <span
                  v-else
                  class="text-medium-emphasis"
                >—</span>
              </td>
              <td class="text-end">
                {{ formatHours(s.regular_hours) }}
              </td>
              <td class="text-end text-medium-emphasis">
                {{ s.regular_slots }}
              </td>
              <td class="text-end">
                {{ formatHours(s.overtime_hours) }}
              </td>
              <td class="text-end text-medium-emphasis">
                {{ s.ot_slots }}
              </td>
              <td class="text-end">
                {{ minutesToHours(s.total_break_minutes) }}
              </td>
              <td>
                <VChip
                  :color="statusColor(s)"
                  size="small"
                  label
                >
                  {{ statusLabel(s) }}
                </VChip>
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
                {{ formatHours(detailTotals.regular) }}
              </td>
              <td class="text-end text-medium-emphasis">
                {{ detailTotals.regularSlots }}
              </td>
              <td class="text-end">
                {{ formatHours(detailTotals.overtime) }}
              </td>
              <td class="text-end text-medium-emphasis">
                {{ detailTotals.otSlots }}
              </td>
              <td class="text-end">
                {{ minutesToHours(detailTotals.breakMinutes) }}
              </td>
              <td />
            </tr>
            <tr v-if="summaries.length === 0 && !loading">
              <td
                colspan="9"
                class="text-center text-medium-emphasis py-6"
              >
                No daily summaries found for this product in {{ monthLabel }}.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div class="text-caption text-medium-emphasis pa-3">
        {{ detailTotals.days }} day{{ detailTotals.days === 1 ? '' : 's' }} · {{ detailTotalCount }} records loaded for this month
      </div>
    </VCard>

    <VDialog
      v-model="deleteDialog"
      max-width="400"
    >
      <VCard v-if="deleteTarget">
        <VCardTitle class="text-h6">
          Confirm Delete
        </VCardTitle>
        <VCardText>
          Delete payroll record for <strong>{{ deleteTarget.product_name || deleteTarget.product_code || deleteTarget.product_id }}</strong> ({{ deleteTarget.payroll_period_start }} – {{ deleteTarget.payroll_period_end }})?
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

.type-field {
  inline-size: 160px;
}

.status-field {
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

.payroll-table :deep(.col-actions) {
  width: 1%;
  white-space: nowrap;
  vertical-align: middle;
}

.payroll-row {
  cursor: pointer;
}
</style>
