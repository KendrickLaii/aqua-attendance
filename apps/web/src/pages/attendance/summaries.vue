<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listSummariesWithTotal, generateSummaries } from '@/api/attendance/summaries'
import type { AttendanceSummary } from '@/api/attendance/summaries'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const SUMMARY_PAGE_SIZE = 50

const authStore = useAttendanceAuthStore()
const router = useRouter()

const summaries = ref<AttendanceSummary[]>([])
const totalCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const generating = ref(false)
const generateError = ref('')
const generateSuccess = ref('')

const yearMonth = ref('')
const page = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / SUMMARY_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} summary${total === 1 ? '' : 's'}`
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * SUMMARY_PAGE_SIZE + 1
  const to = from + summaries.value.length - 1

  if (totalCount.value <= SUMMARY_PAGE_SIZE)
    return `${totalCount.value} summary${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
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
  await loadSummaries()
})

async function loadSummaries(isRefresh = false, resetPage = false) {
  if (resetPage)
    page.value = 1
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listSummariesWithTotal({
      page: page.value,
      page_size: SUMMARY_PAGE_SIZE,
    })

    summaries.value = result.items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load summaries', e)
    loadError.value = formatApiError(e, 'Failed to load attendance summaries. Please try again.')
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
  generateSuccess.value = ''
  try {
    const result = await generateSummaries(year, month)
    generateSuccess.value = `Generated: ${result.created} created, ${result.updated} updated`
    await loadSummaries(true)
  }
  catch (e) {
    console.error('Failed to generate summaries', e)
    generateError.value = formatApiError(e, 'Could not generate summaries')
  }
  finally {
    generating.value = false
  }
}

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadSummaries(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
  loadSummaries(true)
}

function statusColor(status: string) {
  if (status === 'completed')
    return 'success'
  if (status === 'pending')
    return 'warning'

  return 'grey'
}

function formatHours(h: number) {
  return Number.isFinite(h) ? h.toFixed(2) : '-'
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
          Attendance Summaries
        </h1>
        <p class="text-subtitle-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </p>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex flex-wrap gap-2"
      >
        <VTextField
          v-model="yearMonth"
          label="Year-Month"
          type="month"
          density="compact"
          hide-details
          class="generate-field"
        />
        <VBtn
          color="primary"
          :loading="generating"
          @click="handleGenerate"
        >
          Generate
        </VBtn>
        <VBtn
          icon
          variant="text"
          :loading="refreshing"
          @click="loadSummaries(true)"
        >
          <VIcon>tabler-refresh</VIcon>
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
    >
      {{ generateSuccess }}
    </VAlert>

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

    <div class="summaries-table-scroll">
      <VTable
        class="summaries-table"
        density="compact"
        hover
      >
        <thead>
          <tr>
            <th>Date</th>
            <th>Product</th>
            <th>First In</th>
            <th>Last Out</th>
            <th class="text-end">Regular</th>
            <th class="text-end">OT</th>
            <th class="text-end">Break</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in summaries"
            :key="s.id"
          >
            <td>{{ s.summary_date }}</td>
            <td>{{ s.product_id }}</td>
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
              {{ formatHours(s.total_regular_hours) }}
            </td>
            <td class="text-end">
              {{ formatHours(s.total_overtime_hours) }}
            </td>
            <td class="text-end">
              {{ formatHours(s.total_break_hours) }}
            </td>
            <td>
              <VChip
                :color="statusColor(s.status)"
                size="small"
                label
              >
                {{ s.status }}
              </VChip>
            </td>
          </tr>
          <tr v-if="summaries.length === 0 && !loading">
            <td
              colspan="8"
              class="text-center text-medium-emphasis py-6"
            >
              No summaries found. Pick a month and click Generate.
            </td>
          </tr>
        </tbody>
      </VTable>
    </div>

    <div class="d-flex align-center justify-space-between mt-3">
      <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
      <div class="d-flex align-center gap-2">
        <VBtn
          size="small"
          variant="text"
          :disabled="!hasPrevPage"
          @click="goToPrevPage"
        >
          <VIcon>tabler-chevron-left</VIcon>
        </VBtn>
        <span class="text-caption">{{ page }} / {{ totalPages }}</span>
        <VBtn
          size="small"
          variant="text"
          :disabled="!hasNextPage"
          @click="goToNextPage"
        >
          <VIcon>tabler-chevron-right</VIcon>
        </VBtn>
      </div>
    </div>
  </VContainer>
</template>

<style scoped lang="scss">
.generate-field {
  inline-size: 160px;
}

.summaries-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.summaries-table :deep(th) {
  white-space: nowrap;
}
</style>
