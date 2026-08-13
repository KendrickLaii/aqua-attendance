<script setup lang="ts">
import { generateSummaries, getSummaryOverviewStats, listSummariesWithTotal, listSummaryOverview } from '@/api/attendance/summaries'
import type { AttendanceSummary, SummaryOverviewItem, SummaryOverviewStats } from '@/api/attendance/summaries'
import SummaryDateCell from '@/components/attendance/SummaryDateCell.vue'
import { formatAttendanceDateTime, isAutoCheckoutSummaryDay } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { formatSummaryGenerateMessage } from '@/utils/formatGenerateResult'

definePage({ meta: {} })

type DetailStatus = 'all' | 'complete' | 'needs_review' | 'incomplete' | 'weekend'

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
const router = useRouter()

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

useAutoClearAlerts(generateSuccess, generateError, loadError)

const filterUnitType = ref('staff')
const searchQuery = ref('')
const selectedUnit = ref<SummaryOverviewItem | null>(null)
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
  { title: 'Needs review', value: 'needs_review' },
  { title: 'Incomplete', value: 'incomplete' },
  { title: 'Weekend', value: 'weekend' },
]

const isDetailView = computed(() => !!selectedUnit.value)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  if (isDetailView.value && selectedUnit.value)
    return `${selectedUnit.value.unit_name || selectedUnit.value.unit_code} · ${monthLabel.value}`

  const selectedTypeLabel = typeOptions.find(o => o.value === filterUnitType.value)?.title ?? 'All types'

  return `${monthLabel.value} · ${selectedTypeLabel} · ${overviewTotalCount.value} unit${overviewTotalCount.value === 1 ? '' : 's'}`
})

const overviewCaption = computed(() => overviewListCaption(overviewItems.value.length, 'unit'))

function needsManualReview(s: AttendanceSummary) {
  return !s.is_complete || isAutoCheckoutSummaryDay(s)
}

function isMissingCheckIn(s: AttendanceSummary) {
  return !s.first_check_in && !!s.last_check_out
}

const visibleSummaries = computed(() => {
  if (detailStatus.value === 'weekend')
    return summaries.value.filter(s => s.is_weekend)
  if (detailStatus.value === 'complete')
    return summaries.value.filter(s => s.is_complete && !isAutoCheckoutSummaryDay(s))
  if (detailStatus.value === 'needs_review')
    return summaries.value.filter(s => needsManualReview(s))
  if (detailStatus.value === 'incomplete')
    return summaries.value.filter(s => !s.is_complete)

  return summaries.value
})

const detailTotals = computed(() => {
  const regular = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.regular_hours), 0)
  const overtime = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.overtime_hours), 0)
  const regularSlots = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.regular_slots), 0)
  const otSlots = visibleSummaries.value.reduce((sum, s) => sum + safeNumber(s.ot_slots), 0)
  const autoCheckoutDays = visibleSummaries.value.filter(s => isAutoCheckoutSummaryDay(s)).length
  const incompleteDays = visibleSummaries.value.filter(s => !s.is_complete).length
  const needsReviewDays = visibleSummaries.value.filter(s => needsManualReview(s)).length

  return {
    regular,
    overtime,
    regularSlots,
    otSlots,
    days: visibleSummaries.value.length,
    autoCheckoutDays,
    incompleteDays,
    needsReviewDays,

    /** Unreliable while incomplete / auto-checkout days are in the visible set */
    reliable: needsReviewDays === 0,
  }
})

function formatDayHours(s: AttendanceSummary, hours: number) {
  if (!s.is_complete)
    return '—'

  return formatHours(hours)
}

function formatDaySlots(s: AttendanceSummary, slots: number) {
  if (!s.is_complete)
    return '—'

  return String(slots)
}

function formatTotalHours(hours: number) {
  if (!detailTotals.value.reliable)
    return '—'

  return formatHours(hours)
}

function formatTotalSlots(slots: number) {
  if (!detailTotals.value.reliable)
    return '—'

  return String(slots)
}

const needsReviewReminder = computed(() => {
  // Count from the loaded month set (not the active filter) so the banner stays useful.
  const autoCheckout = summaries.value.filter(s => isAutoCheckoutSummaryDay(s)).length
  const incomplete = summaries.value.filter(s => !s.is_complete).length
  const total = summaries.value.filter(s => needsManualReview(s)).length

  return { autoCheckout, incomplete, total }
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

watch([yearMonth, filterUnitType], () => {
  selectedUnit.value = null
  detailStatus.value = 'all'
  resetOverviewPage()
  loadData()
})

watch(detailStatus, () => {
  if (selectedUnit.value)
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
  if (selectedUnit.value)
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
      unit_type: filterUnitType.value || undefined,
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
  if (!range || !selectedUnit.value)
    return

  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listSummariesWithTotal({
      unit_id: selectedUnit.value.unit_id,
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
  selectedUnit.value = item
  detailStatus.value = 'all'
  loadDetail()
}

function backToOverview() {
  selectedUnit.value = null
  summaries.value = []
  detailStatus.value = 'all'
}

function onOverviewPageSizeChange() {
  resetOverviewPage()
  loadOverview(true)
}

function detailStatusQueryValue() {
  // Complete / Needs review / Weekend are refined client-side (auto-checkout vs real out).
  // Incomplete still uses API is_complete=false for a tighter payload.
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
  if (isMissingCheckIn(s))
    return 'Incomplete'
  if (isAutoCheckoutSummaryDay(s))
    return 'Needs review'
  if (!s.is_complete)
    return 'Incomplete'

  return 'Complete'
}

function statusIcon(s: AttendanceSummary) {
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

const statusFilterIconMap: Record<DetailStatus, string> = {
  all: 'ri-list-check',
  complete: 'ri-checkbox-circle-line',
  needs_review: 'ri-alarm-warning-line',
  incomplete: 'ri-error-warning-line',
  weekend: 'ri-calendar-2-line',
}

function statusFilterIcon(status: DetailStatus) {
  return statusFilterIconMap[status] ?? 'ri-list-check'
}

function statusColor(s: AttendanceSummary) {
  if (s.is_holiday || s.is_weekend)
    return 'info'
  if (needsManualReview(s))
    return 'warning'

  return 'success'
}

function openAttendanceLogForUnit() {
  const unitId = selectedUnit.value?.unit_id
  if (!unitId) {
    router.push({ path: '/attendance/log' })

    return
  }

  router.push({
    path: '/attendance/log',
    query: { unit_id: unitId },
  })
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
          v-model="filterUnitType"
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
                Unit
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
              :key="item.unit_id"
              class="summary-row"
              @click="openDetail(item)"
            >
              <td>
                <div class="font-weight-medium">
                  {{ item.unit_name || '—' }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ item.unit_code || item.unit_id }}
                </div>
              </td>
              <td>
                <VChip
                  :color="typeColor(item.unit_type)"
                  size="small"
                  label
                  :prepend-icon="item.unit_type === 'staff' ? 'ri-user-line' : 'ri-graduation-cap-line'"
                >
                  {{ typeLabel(item.unit_type) }}
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
              {{ selectedUnit?.unit_name || selectedUnit?.unit_code }}
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
            {{ formatTotalHours(detailTotals.regular) }} regular · {{ formatTotalSlots(detailTotals.regularSlots) }} slots
          </VChip>
          <VChip
            color="info"
            variant="tonal"
            label
            prepend-icon="ri-flashlight-line"
          >
            {{ formatTotalHours(detailTotals.overtime) }} OT · {{ formatTotalSlots(detailTotals.otSlots) }} slots
          </VChip>
          <VChip
            v-if="detailTotals.autoCheckoutDays > 0"
            color="warning"
            variant="tonal"
            label
            prepend-icon="ri-time-line"
            title="Days closed by day-boundary auto checkout (23:59)"
          >
            {{ detailTotals.autoCheckoutDays }} auto checkout
          </VChip>
          <VChip
            v-if="detailTotals.needsReviewDays > 0"
            color="warning"
            variant="tonal"
            label
            prepend-icon="ri-alarm-warning-line"
            title="Incomplete or auto-closed days that need a real check-out"
          >
            {{ detailTotals.needsReviewDays }} need review
          </VChip>
        </div>
      </VCardTitle>
      <VCardText
        v-if="needsReviewReminder.total > 0"
        class="pb-0"
      >
        <VAlert
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          <div class="d-flex flex-wrap align-center justify-space-between gap-2">
            <div>
              <strong>{{ needsReviewReminder.total }}</strong> Incomplete record{{ needsReviewReminder.total === 1 ? '' : 's' }}.
              <!--
                <span
                v-if="needsReviewReminder.autoCheckout || needsReviewReminder.incomplete"
                class="text-medium-emphasis"
                >
                (
                <template v-if="needsReviewReminder.autoCheckout">{{ needsReviewReminder.autoCheckout }} auto checkout</template>
                <template v-if="needsReviewReminder.autoCheckout && needsReviewReminder.incomplete"> · </template>
                <template v-if="needsReviewReminder.incomplete">{{ needsReviewReminder.incomplete }} incomplete</template>
                ).
                </span>
              -->
              Make sure all data are complete and generate again
            </div>
            <div class="d-flex flex-wrap gap-2">
              <VBtn
                size="small"
                variant="tonal"
                color="warning"
                prepend-icon="ri-filter-line"
                @click="detailStatus = 'needs_review'"
              >
                Show incomplete only
              </VBtn>
              <VBtn
                size="small"
                color="warning"
                prepend-icon="ri-edit-box-line"
                @click="openAttendanceLogForUnit"
              >
                Attendance Log
              </VBtn>
            </div>
          </div>
        </VAlert>
      </VCardText>
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
                  {{ formatDayHours(s, s.regular_hours) }}
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
                  {{ formatDaySlots(s, s.regular_slots) }}
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
                  {{ formatDayHours(s, s.overtime_hours) }}
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
                  {{ formatDaySlots(s, s.ot_slots) }}
                </span>
              </td>
              <td>
                <div class="d-flex flex-wrap align-center gap-1">
                  <VChip
                    :color="statusColor(s)"
                    size="small"
                    label
                    :prepend-icon="statusIcon(s)"
                  >
                    {{ statusLabel(s) }}
                  </VChip>
                  <!--
                    <AutoCheckoutChip
                    :notes="s.attendance_notes"
                    :last-check-out="s.last_check_out"
                    />
                    <span
                    v-if="needsManualReview(s)"
                    class="text-caption text-warning"
                    :title="s.attendance_notes || 'Add or replace the missing check-in/out with Manual correction on Attendance Log, then Generate summaries again'"
                    >
                    {{ reviewHint(s) }}
                    </span>
                  -->
                </div>
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
                <span
                  class="cell-metric"
                  :title="detailTotals.reliable ? 'Regular hours total' : 'Total hidden while incomplete / needs-review days are present'"
                >
                  <VIcon
                    icon="ri-time-line"
                    size="14"
                    class="text-success"
                  />
                  {{ formatTotalHours(detailTotals.regular) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric text-medium-emphasis"
                  :title="detailTotals.reliable ? 'Regular slots total' : 'Total hidden while incomplete / needs-review days are present'"
                >
                  <VIcon
                    icon="ri-grid-line"
                    size="14"
                  />
                  {{ formatTotalSlots(detailTotals.regularSlots) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric"
                  :title="detailTotals.reliable ? 'Overtime hours total' : 'Total hidden while incomplete / needs-review days are present'"
                >
                  <VIcon
                    icon="ri-flashlight-line"
                    size="14"
                    class="text-info"
                  />
                  {{ formatTotalHours(detailTotals.overtime) }}
                </span>
              </td>
              <td class="text-end">
                <span
                  class="cell-metric text-medium-emphasis"
                  :title="detailTotals.reliable ? 'Overtime slots total' : 'Total hidden while incomplete / needs-review days are present'"
                >
                  <VIcon
                    icon="ri-apps-2-line"
                    size="14"
                  />
                  {{ formatTotalSlots(detailTotals.otSlots) }}
                </span>
              </td>
              <td />
            </tr>
            <tr v-if="visibleSummaries.length === 0 && !loading">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-6"
              >
                {{ detailStatus === 'needs_review'
                  ? 'No days need review for this month.'
                  : 'No daily records match this status filter.' }}
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
