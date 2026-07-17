<script setup lang="ts">
import { generateSummaries, getSummaryOverviewStats, listSummariesWithTotal, listSummaryOverview } from '@/api/attendance/summaries'
import type { AttendanceSummary, SummaryOverviewItem, SummaryOverviewStats } from '@/api/attendance/summaries'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatSummaryGenerateMessage } from '@/utils/formatGenerateResult'

definePage({ meta: {} })

type DetailStatus = 'all' | 'complete' | 'incomplete' | 'weekend'

const DETAIL_PAGE_SIZE = 100
const {
  page: overviewPage,
  pageSize: overviewPageSize,
  pageSizeOptions: overviewPageSizeOptions,
  totalCount: overviewTotalCount,
  totalPages: overviewTotalPages,
  listCaption: overviewListCaption,
  resetPage: resetOverviewPage,
} = usePagedList({ pageSize: 200, pageSizeOptions: [40, 100, 200] })

const { ensureAccess } = useAttendanceAdminGate()
const { yearMonth, monthDateRange, monthLabel, changeMonth, toCurrentMonth } = useYearMonth()

const overviewItems = ref<SummaryOverviewItem[]>([])
const overviewStats = ref<SummaryOverviewStats | null>(null)
const summaries = ref<AttendanceSummary[]>([])
const detailTotalCount = ref(0)

const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const generating = ref(false)
const generateError = ref('')
const generateSuccess = ref<{ title: string; detail?: string } | null>(null)

const filterProductType = ref('staff')
const searchQuery = ref('')
const selectedProduct = ref<SummaryOverviewItem | null>(null)
const detailStatus = ref<DetailStatus>('all')

let searchDebounceTimer: ReturnType<typeof setTimeout> | undefined

const typeOptions = [
  { title: 'All types', value: '' },
  { title: 'Staff', value: 'staff' },
  { title: 'Student', value: 'student' },
]

const statusOptions: { title: string; value: DetailStatus }[] = [
  { title: 'All', value: 'all' },
  { title: 'Complete', value: 'complete' },
  { title: 'Incomplete', value: 'incomplete' },
  { title: 'Weekend', value: 'weekend' },
]

const isDetailView = computed(() => !!selectedProduct.value)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  if (isDetailView.value && selectedProduct.value)
    return `${selectedProduct.value.product_name || selectedProduct.value.product_code} · ${monthLabel.value}`

  const selectedTypeLabel = typeOptions.find(o => o.value === filterProductType.value)?.title ?? 'All types'

  return `${monthLabel.value} · ${selectedTypeLabel} · ${overviewTotalCount.value} product${overviewTotalCount.value === 1 ? '' : 's'}`
})

const overviewCaption = computed(() => overviewListCaption(overviewItems.value.length, 'product'))

const visibleSummaries = computed(() => {
  if (detailStatus.value !== 'weekend')
    return summaries.value

  return summaries.value.filter(s => s.is_weekend)
})

const detailTotals = computed(() => {
  const regular = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.regular_hours), 0)
  const overtime = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.overtime_hours), 0)
  const regularSlots = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.regular_slots), 0)
  const otSlots = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.ot_slots), 0)

  return { regular, overtime, regularSlots, otSlots, days: visibleSummaries.value.length }
})

const statCards = computed(() => {
  const stats = overviewStats.value
  const people = stats?.people ?? 0
  const days = stats?.days_present ?? 0
  const complete = stats?.days_complete ?? 0
  const regular = safeNumber(stats?.total_regular_hours ?? 0)
  const overtime = safeNumber(stats?.total_overtime_hours ?? 0)
  const completionRate = days > 0 ? `${Math.round((complete / days) * 100)}%` : '-'

  return [
    {
      label: 'People',
      value: String(people),
      hint: 'filtered month total',
      icon: 'ri-group-line',
      color: 'primary',
    },
    {
      label: 'Records',
      value: String(days),
      hint: 'filtered month · daily rows',
      icon: 'ri-calendar-line',
      color: 'secondary',
    },
    {
      label: 'Complete rate',
      value: completionRate,
      hint: `${complete}/${days} complete · month`,
      icon: 'ri-checkbox-circle-line',
      color: 'success',
    },
    {
      label: 'Total hours',
      value: formatHours(regular + overtime),
      hint: `${formatHours(regular)} regular + ${formatHours(overtime)} OT · month`,
      icon: 'ri-time-line',
      color: 'info',
    },
  ]
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return

  toCurrentMonth()
  await loadData()
})

watch([yearMonth, filterProductType], () => {
  selectedProduct.value = null
  detailStatus.value = 'all'
  resetOverviewPage()
  loadData()
})

watch(detailStatus, () => {
  if (selectedProduct.value)
    loadDetail()
})

watch(searchQuery, () => {
  clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => {
    resetOverviewPage()
    loadOverview(true)
  }, 300)
})

async function loadData(isRefresh = false) {
  await loadOverview(isRefresh)
  if (selectedProduct.value)
    await loadDetail(isRefresh)
}

async function loadOverview(isRefresh = false) {
  const range = monthDateRange.value
  if (!range)
    return

  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const overviewParams = {
      date_from: range.date_from,
      date_to: range.date_to,
      product_type: filterProductType.value || undefined,
      search: (searchQuery.value || '').trim() || undefined,
    }
    const [result, stats] = await Promise.all([
      listSummaryOverview({
        ...overviewParams,
        page: overviewPage.value,
        page_size: overviewPageSize.value,
      }),
      getSummaryOverviewStats(overviewParams),
    ])

    overviewItems.value = result.items
    overviewTotalCount.value = result.total
    overviewStats.value = stats
  }
  catch (e) {
    console.error('Failed to load summary overview', e)
    loadError.value = formatApiError(e, 'Failed to load attendance summary overview. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

async function loadDetail(isRefresh = false) {
  const range = monthDateRange.value
  if (!range || !selectedProduct.value)
    return

  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listSummariesWithTotal({
      product_id: selectedProduct.value.product_id,
      date_from: range.date_from,
      date_to: range.date_to,
      is_complete: detailStatusQueryValue(),
      page: 1,
      page_size: DETAIL_PAGE_SIZE,
    })

    summaries.value = result.items
    detailTotalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load summary detail', e)
    loadError.value = formatApiError(e, 'Failed to load attendance summary detail. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

async function handleGenerate() {
  const ym = yearMonth.value
  if (!ym || !/^\d{4}-\d{2}$/.test(ym)) {
    generateError.value = 'Select a valid year-month (YYYY-MM)'

    return
  }

  const [year, month] = ym.split('-').map(Number)

  generating.value = true
  generateError.value = ''
  generateSuccess.value = null
  try {
    const result = await generateSummaries(year, month)

    await loadData(true)

    const existingDays = overviewItems.value.reduce((sum, item) => sum + item.days_present, 0)

    generateSuccess.value = formatSummaryGenerateMessage(result, year, month, existingDays)
  }
  catch (e) {
    console.error('Failed to generate summaries', e)
    generateError.value = formatApiError(e, 'Could not generate summaries')
  }
  finally {
    generating.value = false
  }
}

function openDetail(item: SummaryOverviewItem) {
  selectedProduct.value = item
  detailStatus.value = 'all'
  loadDetail()
}

function backToOverview() {
  selectedProduct.value = null
  summaries.value = []
  detailStatus.value = 'all'
}

function onOverviewPageSizeChange() {
  resetOverviewPage()
  loadOverview(true)
}

function detailStatusQueryValue() {
  if (detailStatus.value === 'complete')
    return true
  if (detailStatus.value === 'incomplete')
    return false

  return undefined
}

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function typeLabel(type: string) {
  return typeOptions.find(o => o.value === type)?.title ?? type
}

function statusLabel(s: AttendanceSummary) {
  if (s.is_holiday)
    return 'Holiday'
  if (s.is_weekend)
    return 'Weekend'

  return s.is_complete ? 'Complete' : 'Incomplete'
}

function statusIcon(s: AttendanceSummary) {
  if (s.is_holiday)
    return 'ri-calendar-event-line'
  if (s.is_weekend)
    return 'ri-calendar-2-line'

  return s.is_complete ? 'ri-checkbox-circle-line' : 'ri-error-warning-line'
}

function statusFilterIcon(status: DetailStatus) {
  switch (status) {
    case 'complete':
      return 'ri-checkbox-circle-line'
    case 'incomplete':
      return 'ri-error-warning-line'
    case 'weekend':
      return 'ri-calendar-2-line'
    default:
      return 'ri-list-check'
  }
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
</script>

<template>
  <VContainer>
    <VRow
      class="mb-3"
      align="center"
    >
      <VCol>
        <h1 class="text-h5 font-weight-bold">
          Attendance Summaries
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
        <VBtn
          color="primary"
          :loading="generating"
          prepend-icon="ri-magic-line"
          title="Build or refresh daily rows from attendance events for this month"
          @click="handleGenerate"
        >
          Generate
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          @click="loadData(true)"
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

    <StatCards
      v-if="!isDetailView"
      :cards="statCards"
    />

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
        <span>Monthly overview</span>
        <div class="d-flex flex-wrap align-center gap-2">
          <VTextField
            v-model="searchQuery"
            placeholder="Search name / code"
            prepend-inner-icon="ri-search-line"
            density="compact"
            hide-details
            clearable
            class="search-field"
          />
          <span class="text-caption text-medium-emphasis">
            {{ overviewCaption || monthLabel }}
          </span>
        </div>
      </VCardTitle>
      <div class="summaries-table-scroll">
        <VTable
          class="summaries-table"
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th>
                Product
              </th>
              <th>
                Type
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Days present"
                >
                  <VIcon
                    icon="ri-calendar-line"
                    size="14"
                  />
                  Days
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Complete days"
                >
                  <VIcon
                    icon="ri-checkbox-circle-line"
                    size="14"
                  />
                  Complete
                </span>
              </th>
              <th class="text-end">
                <span
                  class="th-label"
                  title="Incomplete days"
                >
                  <VIcon
                    icon="ri-error-warning-line"
                    size="14"
                  />
                  Incomplete
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
              <th class="col-actions" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in overviewItems"
              :key="item.product_id"
              class="summary-row"
              @click="openDetail(item)"
            >
              <td>
                <div class="font-weight-medium">
                  {{ item.product_name || '—' }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ item.product_code || item.product_id }}
                </div>
              </td>
              <td>
                <VChip
                  :color="typeColor(item.product_type)"
                  size="small"
                  label
                  :prepend-icon="item.product_type === 'staff' ? 'ri-user-line' : 'ri-graduation-cap-line'"
                >
                  {{ typeLabel(item.product_type) }}
                </VChip>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Days present"
                >
                  <VIcon
                    icon="ri-calendar-line"
                    size="14"
                    class="text-medium-emphasis"
                  />
                  {{ item.days_present }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Complete days"
                >
                  <VIcon
                    icon="ri-checkbox-circle-line"
                    size="14"
                    class="text-success"
                  />
                  {{ item.days_complete }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  title="Incomplete days"
                >
                  <VIcon
                    icon="ri-error-warning-line"
                    size="14"
                    class="text-warning"
                  />
                  {{ item.days_incomplete }}
                </span>
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
                  {{ formatHours(item.total_regular_hours) }}
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
                  {{ item.total_regular_slots }}
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
                  {{ formatHours(item.total_overtime_hours) }}
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
                  {{ item.total_ot_slots }}
                </span>
              </td>
              <td class="col-actions">
                <VBtn
                  variant="text"
                  size="small"
                  prepend-icon="ri-calendar-schedule-line"
                  @click.stop="openDetail(item)"
                >
                  View days
                </VBtn>
              </td>
            </tr>
            <tr v-if="overviewItems.length === 0 && !loading">
              <td
                colspan="10"
                class="text-center text-medium-emphasis py-6"
              >
                No summaries found for {{ monthLabel }}. Click Generate to build them from attendance events.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div class="d-flex align-center justify-space-between pa-3">
        <div class="d-flex align-center gap-2">
          <span class="text-caption text-medium-emphasis">{{ overviewCaption }}</span>
          <VSelect
            v-model="overviewPageSize"
            :items="overviewPageSizeOptions"
            density="compact"
            variant="plain"
            hide-details
            style="max-width: 80px;"
            @update:model-value="onOverviewPageSizeChange"
          />
          <span class="text-caption text-medium-emphasis">per page</span>
        </div>
        <VPagination
          v-model="overviewPage"
          :length="overviewTotalPages"
          :total-visible="5"
          density="compact"
          size="small"
          @update:model-value="loadOverview(true)"
        />
      </div>
    </VCard>

    <VCard v-else>
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
              {{ selectedProduct?.product_name || selectedProduct?.product_code }}
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ monthLabel }}
            </div>
          </div>
        </div>
        <div class="d-flex flex-wrap gap-2">
          <VChip
            color="primary"
            variant="tonal"
            label
            prepend-icon="ri-calendar-line"
          >
            {{ detailTotals.days }} days
          </VChip>
          <VChip
            color="success"
            variant="tonal"
            label
            prepend-icon="ri-time-line"
          >
            {{ formatHours(detailTotals.regular) }} regular · {{ detailTotals.regularSlots }} slots
          </VChip>
          <VChip
            color="info"
            variant="tonal"
            label
            prepend-icon="ri-flashlight-line"
          >
            {{ formatHours(detailTotals.overtime) }} OT · {{ detailTotals.otSlots }} slots
          </VChip>
        </div>
      </VCardTitle>
      <VCardText class="pb-0">
        <VChipGroup
          v-model="detailStatus"
          mandatory
          selected-class="text-primary"
        >
          <VChip
            v-for="option in statusOptions"
            :key="option.value"
            :value="option.value"
            :prepend-icon="statusFilterIcon(option.value)"
            label
          >
            {{ option.title }}
          </VChip>
        </VChipGroup>
      </VCardText>
      <div class="summaries-table-scroll">
        <VTable
          class="summaries-table"
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
              <th>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in visibleSummaries"
              :key="s.id"
            >
              <td>{{ s.summary_date }}</td>
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
                  <span class="text-caption">{{ s.first_check_in.slice(0, 16).replace('T', ' ') }}</span>
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
                  <span class="text-caption">{{ s.last_check_out.slice(0, 16).replace('T', ' ') }}</span>
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
                <VChip
                  :color="statusColor(s)"
                  size="small"
                  label
                  :prepend-icon="statusIcon(s)"
                >
                  {{ statusLabel(s) }}
                </VChip>
              </td>
            </tr>
            <tr
              v-if="visibleSummaries.length > 0"
              class="font-weight-bold"
            >
              <td>Total</td>
              <td />
              <td />
              <td class="text-end">
                <span class="cell-metric">
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                    class="text-success"
                  />
                  {{ formatHours(detailTotals.regular) }}
                </span>
              </td>
              <td class="text-end">
                <span class="cell-metric text-medium-emphasis">
                  <VIcon
                    icon="ri-grid-line"
                    size="14"
                  />
                  {{ detailTotals.regularSlots }}
                </span>
              </td>
              <td class="text-end">
                <span class="cell-metric">
                  <VIcon
                    icon="ri-flashlight-line"
                    size="14"
                    class="text-info"
                  />
                  {{ formatHours(detailTotals.overtime) }}
                </span>
              </td>
              <td class="text-end">
                <span class="cell-metric text-medium-emphasis">
                  <VIcon
                    icon="ri-apps-2-line"
                    size="14"
                  />
                  {{ detailTotals.otSlots }}
                </span>
              </td>
              <td />
            </tr>
            <tr v-if="visibleSummaries.length === 0 && !loading">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                No daily records match this status filter.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <div class="text-caption text-medium-emphasis pa-3">
        {{ visibleSummaries.length }} shown · {{ detailTotalCount }} records loaded for this month
      </div>
    </VCard>
  </VContainer>
</template>

<style scoped lang="scss">
.month-field {
  inline-size: 160px;
}

.type-field {
  inline-size: 160px;
}

.search-field {
  inline-size: 220px;
}

.summaries-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.summaries-table :deep(th),
.summaries-table :deep(td) {
  white-space: nowrap;
}

.summaries-table :deep(.col-actions) {
  width: 1%;
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

.summary-row {
  cursor: pointer;
}
</style>
