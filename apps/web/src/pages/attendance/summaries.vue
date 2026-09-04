<script setup lang="ts">
import { generateSummaries, getSummaryOverviewStats, listSummariesWithTotal, listSummaryOverview } from '@/api/attendance/summaries'
import type { AttendanceSummary, SummaryOverviewItem, SummaryOverviewStats } from '@/api/attendance/summaries'
import SummariesDetailView from '@/components/attendance/summaries/SummariesDetailView.vue'
import SummariesOverviewTab from '@/components/attendance/summaries/SummariesOverviewTab.vue'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatSummaryGenerateMessage } from '@/utils/formatGenerateResult'
import type { DetailStatus } from '@/utils/summaryDisplay'
import { computeDetailTotals, filterSummariesByDetailStatus, needsManualReview, unitTypeOptions } from '@/utils/summaryDisplay'

definePage({ meta: {} })

const DETAIL_PAGE_SIZE = 100

const {
  page: overviewPage,
  pageSize: overviewPageSize,
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

const isDetailView = computed(() => !!selectedUnit.value)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  if (isDetailView.value && selectedUnit.value)
    return `${selectedUnit.value.unit_name || selectedUnit.value.unit_code} · ${monthLabel.value}`

  const selectedTypeLabel = unitTypeOptions.find(o => o.value === filterUnitType.value)?.title ?? 'All types'

  return `${monthLabel.value} · ${selectedTypeLabel} · ${overviewTotalCount.value} unit${overviewTotalCount.value === 1 ? '' : 's'}`
})

const overviewCaption = computed(() => overviewListCaption(overviewItems.value.length, 'unit'))

const visibleSummaries = computed(() => filterSummariesByDetailStatus(summaries.value, detailStatus.value))

const detailTotals = computed(() => computeDetailTotals(visibleSummaries.value))

const needsReviewReminder = computed(() => summaries.value.filter(s => needsManualReview(s)).length)

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

function onOverviewPageChange(value: number) {
  overviewPage.value = value
  loadOverview(true)
}

function onOverviewPageSizeChange(value: number) {
  overviewPageSize.value = value
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
          :items="unitTypeOptions"
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

    <SummariesOverviewTab
      v-if="!isDetailView"
      :items="overviewItems"
      :stats="overviewStats"
      :loading="loading"
      :month-label="monthLabel"
      :search="searchQuery"
      :caption="overviewCaption"
      :page="overviewPage"
      :page-size="overviewPageSize"
      :page-size-options="[40, 100, 200]"
      :total-pages="overviewTotalPages"
      @update:search="searchQuery = $event"
      @detail="openDetail"
      @page-change="onOverviewPageChange"
      @page-size-change="onOverviewPageSizeChange"
    />

    <SummariesDetailView
      v-else
      :unit="selectedUnit"
      :month-label="monthLabel"
      :summaries="visibleSummaries"
      :totals="detailTotals"
      :detail-status="detailStatus"
      :detail-total-count="detailTotalCount"
      :needs-review-total="needsReviewReminder"
      :loading="loading"
      @back="backToOverview"
      @update:detail-status="detailStatus = $event"
      @open-log="openAttendanceLogForUnit"
    />
  </VContainer>
</template>

<style scoped lang="scss">
.month-field {
  inline-size: 160px;
}

.type-field {
  inline-size: 160px;
}
</style>
