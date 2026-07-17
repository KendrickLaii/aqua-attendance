<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { deletePayrollRecord, generatePayroll, listPayrollRecordsWithTotal, updatePayrollRecord } from '@/api/attendance/payroll'
import type { PayrollRecord } from '@/api/attendance/payroll'
import { listSummariesWithTotal } from '@/api/attendance/summaries'
import type { AttendanceSummary } from '@/api/attendance/summaries'
import { listProducts } from '@/api/attendance/products'
import type { Product } from '@/api/attendance/products'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatPayrollGenerateMessage } from '@/utils/formatGenerateResult'

definePage({ meta: {} })

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
const pageSize = ref(40)
const pageSizeOptions = [10, 20, 40, 60, 100]
const deleteDialog = ref(false)
const deleteTarget = ref<PayrollRecord | null>(null)

const selectedRecord = ref<PayrollRecord | null>(null)
const summaries = ref<AttendanceSummary[]>([])
const detailTotalCount = ref(0)

// Stepper workflow state (configure = Products+Month, result = invoice cards)
const step = ref('configure')
const stepMonth = ref('')
const stepProducts = ref<Product[]>([])
const stepProductsLoading = ref(false)
const stepProductsError = ref('')
const stepSelectedIds = ref<string[]>([])
const stepSearch = ref('')
const generatedRecords = ref<PayrollRecord[]>([])
const viewMode = ref<'wizard' | 'records'>('wizard')

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
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

  return `${monthLabel.value} · ${totalCount.value} record${totalCount.value === 1 ? '' : 's'}`
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

const detailTotals = computed(() => {
  const regular = summaries.value.reduce((sum, s) => sum + safeNumber(s.regular_hours), 0)
  const regularSlots = summaries.value.reduce((sum, s) => sum + safeNumber(s.regular_slots), 0)
  const overtime = summaries.value.reduce((sum, s) => sum + safeNumber(s.overtime_hours), 0)
  const otSlots = summaries.value.reduce((sum, s) => sum + safeNumber(s.ot_slots), 0)

  return { regular, regularSlots, overtime, otSlots, days: summaries.value.length }
})

const stepParsedMonth = computed(() => {
  const ym = stepMonth.value
  if (!ym || !/^\d{4}-\d{2}$/.test(ym))
    return null

  const [year, month] = ym.split('-').map(Number)

  return { year, month }
})

const stepMonthLabel = computed(() => {
  const parsed = stepParsedMonth.value
  if (!parsed)
    return 'Select a month'

  return new Date(parsed.year, parsed.month - 1, 1).toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
})

const stepFilteredProducts = computed(() => {
  const q = stepSearch.value.trim().toLowerCase()
  if (!q)
    return stepProducts.value

  return stepProducts.value.filter(p =>
    p.full_name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q),
  )
})

const stepAllSelected = computed({
  get: () => stepProducts.value.length > 0 && stepSelectedIds.value.length === stepProducts.value.length,
  set: (val: boolean) => {
    stepSelectedIds.value = val ? stepProducts.value.map(p => p.id) : []
  },
})

const stepSelectedCount = computed(() => stepSelectedIds.value.length)

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
  stepMonth.value = yearMonth.value
  await loadRecords()
  if (viewMode.value === 'wizard')
    loadStepProducts()
})

watch([yearMonth, filterStatus], () => {
  selectedRecord.value = null
  summaries.value = []
  loadRecords(true, true)
})

watch(pageSize, () => {
  page.value = 1
  loadRecords(true)
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

const editAdj1 = ref(0)
const editAdj2 = ref(0)
const editAdj1Remark = ref('')
const editAdj2Remark = ref('')
const editGross = ref(0)
const editNet = ref(0)

function openDetail(record: PayrollRecord) {
  selectedRecord.value = record
  summaries.value = []
  editAdj1.value = record.adjustment_1 ?? 0
  editAdj2.value = record.adjustment_2 ?? 0
  editAdj1Remark.value = record.adjustment_1_remark ?? ''
  editAdj2Remark.value = record.adjustment_2_remark ?? ''
  editGross.value = record.gross_pay
  editNet.value = record.net_pay
  loadDetail()
}

function onAdjChange() {
  if (!selectedRecord.value)
    return
  const r = selectedRecord.value
  const gross = r.base_salary + r.overtime_pay + r.holiday_pay + (editAdj1.value || 0)
  const net = gross + (editAdj2.value || 0)

  editGross.value = gross
  editNet.value = net
  updatePayrollRecord(r.id, {
    adjustment_1: editAdj1.value || 0,
    adjustment_2: editAdj2.value || 0,
    adjustment_1_remark: editAdj1Remark.value || null,
    adjustment_2_remark: editAdj2Remark.value || null,
    gross_pay: gross,
    net_pay: net,
  }).then(updated => {
    r.adjustment_1 = updated.adjustment_1
    r.adjustment_2 = updated.adjustment_2
    r.adjustment_1_remark = updated.adjustment_1_remark
    r.adjustment_2_remark = updated.adjustment_2_remark
    r.gross_pay = updated.gross_pay
    r.net_pay = updated.net_pay
  }).catch(e => {
    console.error('Failed to update adjustments', e)
  })
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

function resetWizard() {
  step.value = 'configure'
  stepMonth.value = yearMonth.value
  stepSearch.value = ''
  stepProducts.value = []
  stepSelectedIds.value = []
  stepProductsError.value = ''
  generateError.value = ''
  generateSuccess.value = null
  generatedRecords.value = []
}

function showWizard() {
  resetWizard()
  viewMode.value = 'wizard'
  selectedRecord.value = null
  loadStepProducts()
  summaries.value = []
}

function showRecords() {
  viewMode.value = 'records'
  loadRecords(true, true)
}

async function loadStepProducts() {
  stepProductsLoading.value = true
  stepProductsError.value = ''
  try {
    const items = await listProducts({ product_type: 'staff', page_size: 200 })

    stepProducts.value = [...items].sort((a, b) => a.full_name.localeCompare(b.full_name))
    stepSelectedIds.value = stepProducts.value.map(p => p.id)
  }
  catch (e) {
    console.error('Failed to load products for payroll generation', e)
    stepProductsError.value = formatApiError(e, 'Failed to load products')
  }
  finally {
    stepProductsLoading.value = false
  }
}

watch(step, newStep => {
  if (newStep === 'configure')
    loadStepProducts()
})

function toggleStepProduct(id: string) {
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
    generateError.value = 'Select at least one product'

    return
  }

  const { year, month } = parsed
  const idsToSend = stepAllSelected.value ? undefined : stepSelectedIds.value

  generating.value = true
  generateError.value = ''
  generateSuccess.value = null
  generatedRecords.value = []
  try {
    await generatePayroll(year, month, 'staff', idsToSend)

    generateSuccess.value = formatPayrollGenerateMessage({ created: stepSelectedCount.value, updated: 0, skipped: 0 }, year, month)
    filterProductType.value = 'staff'
    yearMonth.value = stepMonth.value

    const result = await listPayrollRecordsWithTotal({
      product_type: 'staff',
      year,
      month,
      page: 1,
      page_size: 200,
    })

    generatedRecords.value = result.items.filter(r =>
      idsToSend ? idsToSend.includes(r.product_id) : true,
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

function formatHours(h: number) {
  return Number.isFinite(h) ? h.toFixed(2) : '-'
}

function safeNumber(value: number) {
  return Number.isFinite(value) ? value : 0
}

function formatCurrency(n: number | null | undefined) {
  if (n === null || n === undefined)
    return '-'

  return Number.isFinite(n) ? n.toFixed(2) : '-'
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
        class="d-flex gap-2"
      >
        <VBtn
          :variant="viewMode === 'wizard' ? 'flat' : 'tonal'"
          color="primary"
          prepend-icon="ri-magic-line"
          @click="showWizard"
        >
          Generate
        </VBtn>
        <VBtn
          :variant="viewMode === 'records' ? 'flat' : 'tonal'"
          color="primary"
          prepend-icon="ri-file-list-line"
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
      <VStepper
        v-model="step"
        class="payroll-stepper"
      >
        <VStepperHeader>
          <VStepperItem
            title="Configure"
            value="configure"
            editable
          />
          <VDivider />
          <VStepperItem
            title="Result"
            value="result"
            editable
          />
        </VStepperHeader>

        <VStepperWindow>
          <!-- Step 1: Configure (Type + Products + Month) -->
          <VStepperWindowItem value="configure">
            <div class="pa-4">
              <h2 class="text-h6 mb-4">
                Configure payroll run
              </h2>

              <VAlert
                v-if="generateError"
                type="error"
                variant="tonal"
                density="compact"
                class="mb-4"
              >
                {{ generateError }}
              </VAlert>

              <!-- Products -->
              <h3 class="text-subtitle-2 font-weight-medium mb-2">
                1. Staff products
              </h3>
              <div class="d-flex align-center gap-3 mb-3">
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
                />
                <VSpacer />
                <span class="text-caption text-medium-emphasis">
                  {{ stepProducts.length }} loaded · {{ stepSelectedCount }} selected
                </span>
              </div>

              <VProgressLinear
                v-if="stepProductsLoading"
                indeterminate
                color="primary"
                class="mb-2"
              />
              <VAlert
                v-else-if="stepProductsError"
                type="error"
                variant="tonal"
                density="compact"
                class="mb-2"
              >
                {{ stepProductsError }}
              </VAlert>

              <div class="product-list">
                <VListItem
                  v-for="p in stepFilteredProducts"
                  :key="p.id"
                  :title="p.full_name"
                  :subtitle="p.code"
                  density="comfortable"
                  class="product-list-item"
                  @click="toggleStepProduct(p.id)"
                >
                  <template #prepend>
                    <VCheckbox
                      :model-value="stepSelectedIds.includes(p.id)"
                      density="comfortable"
                      hide-details
                      @click.stop="toggleStepProduct(p.id)"
                    />
                  </template>
                </VListItem>
                <div
                  v-if="!stepProductsLoading && stepFilteredProducts.length === 0"
                  class="text-center text-medium-emphasis py-8"
                >
                  No staff products found.
                </div>
              </div>

              <!-- Month -->
              <h3 class="text-subtitle-2 font-weight-medium mb-2 mt-6">
                2. Payroll month
              </h3>
              <div
                class="d-flex align-center gap-4 mb-4 flex-wrap"
                :class="{ 'opacity-50': stepSelectedCount === 0 }"
              >
                <VTextField
                  v-model="stepMonth"
                  label="Month"
                  type="month"
                  density="compact"
                  :disabled="stepSelectedCount === 0"
                  style="max-inline-size: 220px;"
                />
                <VAlert
                  type="info"
                  variant="tonal"
                  density="compact"
                  class="mb-0"
                >
                  Generating for
                  <strong>{{ stepSelectedCount }}</strong>
                  staff product{{ stepSelectedCount === 1 ? '' : 's' }}
                  · <strong>{{ stepMonthLabel }}</strong>
                </VAlert>
              </div>

              <div class="d-flex justify-end mt-6">
                <VBtn
                  color="primary"
                  :loading="generating"
                  :disabled="stepSelectedCount === 0"
                  prepend-icon="ri-magic-line"
                  @click="handleGenerate"
                >
                  Generate payroll
                </VBtn>
              </div>
            </div>
          </VStepperWindowItem>

          <!-- Step 2: Invoice-style results -->
          <VStepperWindowItem value="result">
            <div class="pa-4">
              <div class="d-flex align-center justify-space-between mb-4">
                <div>
                  <h2 class="text-h6 mb-0">
                    Payroll result
                  </h2>
                  <p class="text-body-2 text-medium-emphasis mb-0">
                    {{ stepMonthLabel }} · {{ generatedRecords.length }} record{{ generatedRecords.length === 1 ? '' : 's' }}
                  </p>
                </div>
                <VBtn
                  variant="tonal"
                  color="primary"
                  prepend-icon="ri-add-line"
                  @click="resetWizard"
                >
                  New run
                </VBtn>
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
                      <template #title>
                        <div class="d-flex align-center gap-2">
                          <span class="text-h6 font-weight-bold">
                            {{ record.product_name || '—' }}
                          </span>
                          <VChip
                            :color="statusColorMap[record.status] ?? 'grey'"
                            size="small"
                            label
                          >
                            {{ record.status }}
                          </VChip>
                        </div>
                      </template>
                      <template #subtitle>
                        <div class="text-medium-emphasis">
                          {{ record.product_code || record.product_id }}
                        </div>
                      </template>
                    </VCardItem>
                    <VDivider />
                    <VCardText class="invoice-body">
                      <div class="d-flex justify-space-between mb-4">
                        <div>
                          <div class="text-caption text-medium-emphasis">
                            Period
                          </div>
                          <div class="font-weight-medium">
                            {{ record.payroll_period_start }} – {{ record.payroll_period_end }}
                          </div>
                        </div>
                        <div class="text-end">
                          <div class="text-caption text-medium-emphasis">
                            Work days
                          </div>
                          <div class="font-weight-medium">
                            {{ record.total_work_days }}
                          </div>
                        </div>
                      </div>

                      <div class="invoice-grid">
                        <div class="invoice-cell">
                          <span class="text-caption text-medium-emphasis">Regular</span>
                          <span class="font-weight-medium">{{ formatHours(record.total_regular_hours) }} h</span>
                          <span class="text-caption text-medium-emphasis">{{ record.regular_slots }} slots</span>
                        </div>
                        <div class="invoice-cell">
                          <span class="text-caption text-medium-emphasis">Overtime</span>
                          <span class="font-weight-medium">{{ formatHours(record.total_overtime_hours) }} h</span>
                          <span class="text-caption text-medium-emphasis">{{ record.ot_slots }} slots</span>
                        </div>
                        <div class="invoice-cell">
                          <span class="text-caption text-medium-emphasis">Rate</span>
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
                      <div class="invoice-line align-center">
                        <span>Adjustment 1</span>
                        <VTextField
                          v-model.number="record.adjustment_1"
                          type="number"
                          density="compact"
                          variant="outlined"
                          hide-details
                          style="max-inline-size: 120px;"
                          @update:model-value="onCardAdjChange(record)"
                        />
                      </div>
                      <VTextField
                        v-model="record.adjustment_1_remark"
                        class="invoice-remark mb-1"
                        placeholder="Remark"
                        density="compact"
                        variant="underlined"
                        hide-details
                        @update:model-value="onCardAdjChange(record)"
                      />
                      <div class="invoice-line total">
                        <span>Gross pay</span>
                        <span class="font-weight-bold">{{ formatCurrency(record.gross_pay) }}</span>
                      </div>
                      <div class="invoice-line align-center">
                        <span>Adjustment 2</span>
                        <VTextField
                          v-model.number="record.adjustment_2"
                          type="number"
                          density="compact"
                          variant="outlined"
                          hide-details
                          style="max-inline-size: 120px;"
                          @update:model-value="onCardAdjChange(record)"
                        />
                      </div>
                      <VTextField
                        v-model="record.adjustment_2_remark"
                        class="invoice-remark mb-1"
                        placeholder="Remark"
                        density="compact"
                        variant="underlined"
                        hide-details
                        @update:model-value="onCardAdjChange(record)"
                      />
                      <div class="invoice-line grand">
                        <span>Net pay</span>
                        <span class="text-h6 font-weight-bold text-primary">{{ formatCurrency(record.net_pay) }}</span>
                      </div>
                    </VCardText>
                    <VDivider />
                    <VCardActions class="justify-end">
                      <VBtn
                        v-if="record.status === 'draft' || record.status === 'calculated'"
                        size="small"
                        variant="text"
                        color="success"
                        @click="updateStatus(record, 'approved')"
                      >
                        Approve
                      </VBtn>
                      <VBtn
                        v-if="record.status === 'approved'"
                        size="small"
                        variant="text"
                        color="primary"
                        @click="updateStatus(record, 'paid')"
                      >
                        Pay
                      </VBtn>
                      <VBtn
                        size="small"
                        variant="text"
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
                No payroll records generated. Go back and try again.
              </div>
            </div>
          </VStepperWindowItem>
        </VStepperWindow>
      </VStepper>
    </template>

    <!-- Records mode -->
    <template v-else-if="viewMode === 'records' && !isDetailView">
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
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="3"
        >
          <VSelect
            v-model="filterProductType"
            :items="[{ title: 'Staff', value: 'staff' }, { title: 'Student', value: 'student' }]"
            item-title="title"
            item-value="value"
            label="Type"
            density="compact"
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
          <span>Monthly payroll records</span>
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
                <th>Product</th>
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
                  No payroll records found for {{ monthLabel }}.
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
      <VCardText class="pb-0">
        <VRow dense>
          <VCol
            cols="12"
            sm="3"
          >
            <VTextField
              v-model.number="editAdj1"
              label="Adjustment 1"
              type="number"
              density="compact"
              hide-details
              @update:model-value="onAdjChange"
            />
            <VTextField
              v-model="editAdj1Remark"
              class="mt-2"
              label="Remark"
              density="compact"
              hide-details
              @update:model-value="onAdjChange"
            />
            <div class="text-caption text-medium-emphasis mt-1">
              Base + OT + Holiday + Adj1 = Gross
            </div>
          </VCol>
          <VCol
            cols="12"
            sm="3"
          >
            <VTextField
              v-model.number="editAdj2"
              label="Adjustment 2"
              type="number"
              density="compact"
              hide-details
              @update:model-value="onAdjChange"
            />
            <VTextField
              v-model="editAdj2Remark"
              class="mt-2"
              label="Remark"
              density="compact"
              hide-details
              @update:model-value="onAdjChange"
            />
            <div class="text-caption text-medium-emphasis mt-1">
              Gross + Adj2 = Net
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
              {{ formatCurrency(editGross) }}
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
              {{ formatCurrency(editNet) }}
            </div>
          </VCol>
        </VRow>
      </VCardText>
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
              <th>Date</th>
              <th>First In</th>
              <th>Last Out</th>
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
              <th>Status</th>
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
              <td />
            </tr>
            <tr v-if="summaries.length === 0 && !loading">
              <td
                colspan="8"
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
.payroll-stepper {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}

.type-card {
  transition: transform 0.15s ease;

  &:hover {
    transform: translateY(-2px);
  }
}

.product-list {
  max-block-size: 340px;
  overflow-y: auto;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}

.product-list-item {
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

.invoice-remark {
  margin-block-start: -2px;
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
</style>
