<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { getAttendanceDayStats, listAttendanceWithTotal } from '@/api/attendance/events'
import { listProducts } from '@/api/attendance/products'
import type { Product } from '@/api/attendance/products'
import { getAutoCheckoutStatus, triggerAutoCheckout } from '@/api/attendance/autoCheckout'
import type { AttendanceEvent } from '@/api/attendance/events'
import { formatAttendanceDateLabel, formatAttendanceTime, getTodayRangeIso } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

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
const stillCheckedInCount = ref(0)
const autoCheckoutLoading = ref(false)
const autoCheckoutResult = ref('')

const autoCheckoutDialog = ref(false)
const autoCheckoutCandidates = ref<Product[]>([])
const autoCheckoutSelectedIds = ref<string[]>([])
const autoCheckoutCandidatesLoading = ref(false)
const autoCheckoutDialogError = ref('')

const allCandidatesSelected = computed(() =>
  autoCheckoutCandidates.value.length > 0
  && autoCheckoutSelectedIds.value.length === autoCheckoutCandidates.value.length)

const autoCheckoutSaveLabel = computed(() =>
  `Check out ${autoCheckoutSelectedIds.value.length} selected`)

function toggleSelectAllCandidates() {
  autoCheckoutSelectedIds.value = allCandidatesSelected.value
    ? []
    : autoCheckoutCandidates.value.map(p => p.id)
}

const recentEventsCaption = computed(() => {
  if (todayEventTotal.value === 0)
    return ''

  const shown = recentEvents.value.length
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

    const [eventsResult, dayStats, products, checkoutStatus] = await Promise.all([
      listAttendanceWithTotal({ date_from: range.date_from, date_to: range.date_to, page_size: RECENT_EVENTS_LIMIT }),
      getAttendanceDayStats({ date_from: range.date_from, date_to: range.date_to }),
      listProducts({ is_active: true, page_size: 200 }),
      getAutoCheckoutStatus().catch(() => ({ still_checked_in_count: 0 })),
    ])

    const events = eventsResult.items

    todayEventTotal.value = dayStats.total
    recentEvents.value = events
    presentStudentCount.value = products.filter(p => p.product_type === 'student' && p.attendance_status === 'checked_in').length
    presentStaffCount.value = products.filter(p => p.product_type === 'staff' && p.attendance_status === 'checked_in').length
    activeStudentCount.value = products.filter(p => p.product_type === 'student').length
    activeStaffCount.value = products.filter(p => p.product_type === 'staff').length
    todayCheckInsStudent.value = dayStats.check_ins_student
    todayCheckInsStaff.value = dayStats.check_ins_staff
    todayCheckOutsStudent.value = dayStats.check_outs_student
    todayCheckOutsStaff.value = dayStats.check_outs_staff
    stillCheckedInCount.value = checkoutStatus.still_checked_in_count
  }
  catch (e) {
    console.error('Failed to load dashboard', e)
    loadError.value = formatApiError(e, 'Failed to load dashboard data. Please try again.')
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

async function openAutoCheckoutDialog() {
  autoCheckoutDialog.value = true
  autoCheckoutDialogError.value = ''
  autoCheckoutCandidatesLoading.value = true
  autoCheckoutCandidates.value = []
  autoCheckoutSelectedIds.value = []
  try {
    const products = await listProducts({ is_active: true, attendance_status: 'checked_in', page_size: 200 })

    autoCheckoutCandidates.value = products
    autoCheckoutSelectedIds.value = products.map(p => p.id)
  }
  catch (e: unknown) {
    autoCheckoutDialogError.value = formatApiError(e, 'Failed to load checked-in products')
  }
  finally {
    autoCheckoutCandidatesLoading.value = false
  }
}

async function confirmAutoCheckout() {
  if (autoCheckoutSelectedIds.value.length === 0)
    return

  autoCheckoutLoading.value = true
  autoCheckoutResult.value = ''
  try {
    const result = await triggerAutoCheckout({ productIds: [...autoCheckoutSelectedIds.value] })
    autoCheckoutResult.value = result.message
    autoCheckoutDialog.value = false
    await loadDashboard(true)
  }
  catch (e: unknown) {
    autoCheckoutDialogError.value = formatApiError(e, 'Auto-checkout failed')
  }
  finally {
    autoCheckoutLoading.value = false
  }
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
          v-if="authStore.isAdmin"
          variant="outlined"
          color="warning"
          prepend-icon="ri-time-line"
          :loading="autoCheckoutLoading"
          @click="openAutoCheckoutDialog"
        >
          Auto Checkout
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
      <VAlert
        v-if="autoCheckoutResult"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        closable
        @click:close="autoCheckoutResult = ''"
      >
        {{ autoCheckoutResult }}
      </VAlert>

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

      <VRow
        v-if="stillCheckedInCount > 0"
        class="mb-2"
      >
        <VCol cols="12">
          <VCard
            color="warning"
            variant="tonal"
          >
            <VCardText class="d-flex align-center justify-space-between">
              <div>
                <div class="text-h6 font-weight-bold">
                  {{ stillCheckedInCount }}
                </div>
                <div class="text-body-2">
                  Still checked in (pending auto-checkout)
                </div>
              </div>
              <VBtn
                v-if="authStore.isAdmin"
                size="small"
                variant="outlined"
                color="warning"
                :loading="autoCheckoutLoading"
                @click="openAutoCheckoutDialog"
              >
                Review &amp; Run
              </VBtn>
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

    <AttendanceFormDialog
      v-model="autoCheckoutDialog"
      title="Auto Checkout"
      icon="ri-time-line"
      :max-width="560"
      :saving="autoCheckoutLoading"
      :error="autoCheckoutDialogError"
      :save-label="autoCheckoutSaveLabel"
      :form-defaults="false"
      @save="confirmAutoCheckout"
      @cancel="autoCheckoutDialog = false"
      @clear-error="autoCheckoutDialogError = ''"
    >
      <p class="text-body-2 text-medium-emphasis mb-4">
        Select who to check out now. Unselected products stay checked in so you
        can investigate why they never scanned out.
      </p>

      <div
        v-if="autoCheckoutCandidatesLoading"
        class="text-center py-6"
      >
        <VProgressCircular
          indeterminate
          color="primary"
        />
      </div>

      <div
        v-else-if="autoCheckoutCandidates.length === 0"
        class="text-center text-medium-emphasis py-6"
      >
        No products are still checked in.
      </div>

      <template v-else>
        <div class="d-flex align-center justify-space-between mb-2">
          <VBtn
            variant="text"
            size="small"
            @click="toggleSelectAllCandidates"
          >
            {{ allCandidatesSelected ? 'Deselect all' : 'Select all' }}
          </VBtn>
          <span class="text-caption text-medium-emphasis">
            {{ autoCheckoutSelectedIds.length }} / {{ autoCheckoutCandidates.length }} selected
          </span>
        </div>

        <VList
          density="compact"
          max-height="320"
          class="border rounded"
        >
          <VListItem
            v-for="product in autoCheckoutCandidates"
            :key="product.id"
          >
            <template #prepend>
              <VCheckbox
                v-model="autoCheckoutSelectedIds"
                :value="product.id"
                hide-details
                density="compact"
              />
            </template>
            <VListItemTitle>
              {{ product.full_name }}
              <VChip
                :color="product.product_type === 'staff' ? 'info' : 'success'"
                size="x-small"
                label
                class="ms-1"
              >
                {{ product.product_type }}
              </VChip>
            </VListItemTitle>
            <VListItemSubtitle>
              {{ product.code }}
              <span v-if="product.last_event_at">
                · last event {{ formatAttendanceTime(product.last_event_at) }}
              </span>
            </VListItemSubtitle>
          </VListItem>
        </VList>
      </template>
    </AttendanceFormDialog>
  </VContainer>
</template>
