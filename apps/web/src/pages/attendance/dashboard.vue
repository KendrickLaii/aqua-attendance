<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listAttendance } from '@/api/attendance/events'
import { listProducts } from '@/api/attendance/products'
import type { AttendanceEvent } from '@/api/attendance/events'
import { formatAttendanceDateLabel, formatAttendanceTime, getTodayRangeIso } from '@/utils/attendanceDisplay'

definePage({ meta: {} })

const EVENTS_PAGE_SIZE = 200
const RECENT_EVENTS_LIMIT = 20

const authStore = useAttendanceAuthStore()
const router = useRouter()

const recentEvents = ref<AttendanceEvent[]>([])
const presentStudentCount = ref(0)
const presentStaffCount = ref(0)
const todayCheckInsStudent = ref(0)
const todayCheckInsStaff = ref(0)
const todayCheckOutsStudent = ref(0)
const todayCheckOutsStaff = ref(0)
const activeStudentCount = ref(0)
const activeStaffCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
const todayLabel = ref(formatAttendanceDateLabel())
const todayEventTotal = ref(0)
const todayEventsCapped = ref(false)

const recentEventsCaption = computed(() => {
  if (todayEventTotal.value === 0)
    return ''

  const shown = recentEvents.value.length
  if (todayEventsCapped.value)
    return `Showing latest ${shown} of ${EVENTS_PAGE_SIZE}+ events today`
  if (todayEventTotal.value > shown)
    return `Showing latest ${shown} of ${todayEventTotal.value} events today`

  return `Showing all ${todayEventTotal.value} events today`
})

const todayCheckInsTotal = computed(() => todayCheckInsStudent.value + todayCheckInsStaff.value)
const todayCheckOutsTotal = computed(() => todayCheckOutsStudent.value + todayCheckOutsStaff.value)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  return todayLabel.value
})

async function loadDashboard(isRefresh = false) {
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    todayLabel.value = formatAttendanceDateLabel()

    const range = getTodayRangeIso()

    const [events, products] = await Promise.all([
      listAttendance({ date_from: range.date_from, date_to: range.date_to, page_size: EVENTS_PAGE_SIZE }),
      listProducts({ is_active: true, page_size: 200 }),
    ])

    todayEventTotal.value = events.length
    todayEventsCapped.value = events.length >= EVENTS_PAGE_SIZE
    recentEvents.value = events.slice(0, RECENT_EVENTS_LIMIT)
    presentStudentCount.value = products.filter(p => p.product_type === 'student' && p.attendance_status === 'checked_in').length
    presentStaffCount.value = products.filter(p => p.product_type === 'staff' && p.attendance_status === 'checked_in').length
    activeStudentCount.value = products.filter(p => p.product_type === 'student').length
    activeStaffCount.value = products.filter(p => p.product_type === 'staff').length
    todayCheckInsStudent.value = events.filter(e => e.event_type === 'check_in' && e.product_type === 'student').length
    todayCheckInsStaff.value = events.filter(e => e.event_type === 'check_in' && e.product_type === 'staff').length
    todayCheckOutsStudent.value = events.filter(e => e.event_type === 'check_out' && e.product_type === 'student').length
    todayCheckOutsStaff.value = events.filter(e => e.event_type === 'check_out' && e.product_type === 'staff').length
  }
  catch (e) {
    console.error('Failed to load dashboard', e)
    loadError.value = 'Failed to load dashboard data. Please try again.'
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  await loadDashboard()
})

function eventColor(type: string) {
  if (type === 'check_in')
    return 'success'
  if (type === 'check_out')
    return 'warning'

  return 'info'
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol
        cols="12"
        sm="8"
      >
        <div class="text-h5 font-weight-medium">
          Today's Overview
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </div>
      </VCol>
      <VCol
        cols="12"
        sm="4"
        class="d-flex flex-wrap justify-sm-end gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          :disabled="loading"
          @click="loadDashboard(true)"
        >
          Refresh
        </VBtn>
        <VBtn
          variant="outlined"
          :to="{ name: 'attendance-log' }"
          prepend-icon="ri-list-check"
        >
          Full Log
        </VBtn>
      </VCol>
    </VRow>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="loadError = ''"
    >
      {{ loadError }}
      <template #append>
        <VBtn
          variant="text"
          size="small"
          @click="loadDashboard(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VRow
      v-if="loading"
      class="mb-4"
    >
      <VCol
        cols="12"
        class="text-center py-12"
      >
        <VProgressCircular
          indeterminate
          color="primary"
          size="48"
        />
      </VCol>
    </VRow>

    <template v-else>
      <VRow class="mb-2">
        <VCol
          cols="12"
          sm="6"
        >
          <VCard
            color="success"
            variant="tonal"
          >
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">
                {{ presentStudentCount }}
              </div>
              <div class="text-body-1">
                Students Checked In
              </div>
            </VCardText>
          </VCard>
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VCard
            color="info"
            variant="tonal"
          >
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">
                {{ presentStaffCount }}
              </div>
              <div class="text-body-1">
                Staff Checked In
              </div>
            </VCardText>
          </VCard>
        </VCol>
      </VRow>

      <VRow class="mb-4">
        <VCol
          cols="12"
          sm="4"
        >
          <VCard
            color="primary"
            variant="tonal"
          >
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">
                {{ todayCheckInsTotal }}
              </div>
              <div class="text-body-1">
                Check-ins Today
              </div>
              <div class="text-caption text-medium-emphasis mt-1">
                {{ todayCheckInsStudent }} students · {{ todayCheckInsStaff }} staff
              </div>
            </VCardText>
          </VCard>
        </VCol>
        <VCol
          cols="12"
          sm="4"
        >
          <VCard
            color="warning"
            variant="tonal"
          >
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">
                {{ todayCheckOutsTotal }}
              </div>
              <div class="text-body-1">
                Check-outs Today
              </div>
              <div class="text-caption text-medium-emphasis mt-1">
                {{ todayCheckOutsStudent }} students · {{ todayCheckOutsStaff }} staff
              </div>
            </VCardText>
          </VCard>
        </VCol>
        <VCol
          cols="12"
          sm="4"
        >
          <VCard variant="tonal">
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">
                {{ activeStudentCount + activeStaffCount }}
              </div>
              <div class="text-body-1">
                Active Products
              </div>
              <div class="text-caption text-medium-emphasis mt-1">
                {{ activeStudentCount }} students · {{ activeStaffCount }} staff
              </div>
            </VCardText>
          </VCard>
        </VCol>
      </VRow>

      <VCard>
        <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
          <span>Recent Activity Today</span>
          <span
            v-if="recentEventsCaption"
            class="text-caption text-medium-emphasis"
          >
            {{ recentEventsCaption }}
          </span>
        </VCardTitle>
        <VTable>
          <thead>
            <tr>
              <th>Time</th>
              <th>Product</th>
              <th>Type</th>
              <th>Event</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="evt in recentEvents"
              :key="evt.id"
            >
              <td>{{ formatAttendanceTime(evt.recorded_at) }}</td>
              <td>{{ evt.product_name || evt.product_code || evt.product_id }}</td>
              <td>
                <VChip
                  v-if="evt.product_type"
                  :color="evt.product_type === 'staff' ? 'info' : 'success'"
                  size="x-small"
                  label
                >
                  {{ evt.product_type }}
                </VChip>
                <span v-else>—</span>
              </td>
              <td>
                <VChip
                  :color="eventColor(evt.event_type)"
                  size="small"
                  label
                >
                  {{ evt.event_type.replace('_', ' ') }}
                </VChip>
              </td>
              <td>{{ evt.location || '—' }}</td>
            </tr>
            <tr v-if="recentEvents.length === 0">
              <td
                colspan="5"
                class="text-center text-medium-emphasis py-4"
              >
                No events today
              </td>
            </tr>
          </tbody>
        </VTable>
      </VCard>
    </template>
  </VContainer>
</template>
