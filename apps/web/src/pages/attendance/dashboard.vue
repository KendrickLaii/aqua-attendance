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
const presentTotal = computed(() => presentStudentCount.value + presentStaffCount.value)
const activeTotal = computed(() => activeStudentCount.value + activeStaffCount.value)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  return todayLabel.value
})

const presentStatCards = computed(() => [
  {
    label: 'Students present',
    value: String(presentStudentCount.value),
    hint: 'currently checked in',
    icon: 'ri-graduation-cap-line',
    color: 'success',
  },
  {
    label: 'Staff present',
    value: String(presentStaffCount.value),
    hint: 'currently checked in',
    icon: 'ri-user-line',
    color: 'info',
  },
  {
    label: 'Check-ins today',
    value: String(todayCheckInsTotal.value),
    hint: `${todayCheckInsStudent.value} students · ${todayCheckInsStaff.value} staff`,
    icon: 'ri-login-circle-line',
    color: 'primary',
  },
  {
    label: 'Check-outs today',
    value: String(todayCheckOutsTotal.value),
    hint: `${todayCheckOutsStudent.value} students · ${todayCheckOutsStaff.value} staff`,
    icon: 'ri-logout-circle-line',
    color: 'warning',
  },
])

const summaryStatCards = computed(() => [
  {
    label: 'On site now',
    value: String(presentTotal.value),
    hint: `${presentStudentCount.value} students · ${presentStaffCount.value} staff`,
    icon: 'ri-map-pin-user-line',
    color: 'success',
  },
  {
    label: 'Events today',
    value: String(todayEventTotal.value),
    hint: recentEventsCaption.value || 'all event types',
    icon: 'ri-file-list-3-line',
    color: 'primary',
  },
  {
    label: 'Active products',
    value: String(activeTotal.value),
    hint: `${activeStudentCount.value} students · ${activeStaffCount.value} staff`,
    icon: 'ri-group-line',
    color: 'secondary',
  },
  {
    label: 'Pending checkout',
    value: String(stillCheckedInCount.value),
    hint: stillCheckedInCount.value > 0 ? 'needs auto-checkout review' : 'all clear',
    icon: 'ri-time-line',
    color: stillCheckedInCount.value > 0 ? 'warning' : 'success',
  },
])

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

function eventIcon(type: string) {
  if (type === 'check_in')
    return 'ri-login-circle-line'
  if (type === 'check_out')
    return 'ri-logout-circle-line'

  return 'ri-edit-line'
}

function eventTypeLabel(type: string) {
  if (type === 'check_in')
    return 'Check In'
  if (type === 'check_out')
    return 'Check Out'
  if (type === 'manual_correction')
    return 'Manual'

  return type.replaceAll('_', ' ')
}

function typeLabel(type: string) {
  if (type === 'staff')
    return 'Staff'
  if (type === 'student')
    return 'Student'

  return type
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
      class="mb-3"
      align="center"
    >
      <VCol
        cols="12"
        sm="7"
      >
        <h1 class="text-h5 font-weight-bold d-flex align-center gap-2">
          <VIcon
            icon="ri-dashboard-line"
            color="primary"
          />
          Today's Overview
        </h1>
        <p class="text-subtitle-2 text-medium-emphasis mb-0">
          {{ pageSubtitle }}
        </p>
      </VCol>
      <VCol
        cols="12"
        sm="5"
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

    <VProgressLinear
      v-if="loading && !refreshing"
      indeterminate
      color="primary"
      class="mb-4"
    />

    <template v-else>
      <VAlert
        v-if="autoCheckoutResult"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        closable
        prepend-icon="ri-checkbox-circle-line"
        @click:close="autoCheckoutResult = ''"
      >
        {{ autoCheckoutResult }}
      </VAlert>

      <div class="text-subtitle-2 font-weight-medium mb-2 d-flex align-center gap-2">
        <VIcon
          icon="ri-pulse-line"
          size="18"
          color="primary"
        />
        Live status
      </div>
      <StatCards :cards="presentStatCards" />

      <div class="text-subtitle-2 font-weight-medium mb-2 d-flex align-center gap-2">
        <VIcon
          icon="ri-bar-chart-box-line"
          size="18"
          color="primary"
        />
        Today at a glance
      </div>
      <StatCards :cards="summaryStatCards" />

      <VAlert
        v-if="stillCheckedInCount > 0 && authStore.isAdmin"
        type="warning"
        variant="tonal"
        class="mb-4"
        prominent
      >
        <template #prepend>
          <VIcon icon="ri-alarm-warning-line" />
        </template>
        <div class="d-flex flex-wrap align-center justify-space-between gap-2 w-100">
          <div>
            <div class="font-weight-medium">
              {{ stillCheckedInCount }} still checked in
            </div>
            <div class="text-body-2">
              Review and run day-boundary auto-checkout when ready.
            </div>
          </div>
          <VBtn
            size="small"
            variant="flat"
            color="warning"
            prepend-icon="ri-time-line"
            :loading="autoCheckoutLoading"
            @click="openAutoCheckoutDialog"
          >
            Review &amp; Run
          </VBtn>
        </div>
      </VAlert>

      <VCard
        v-if="authStore.isAdmin"
        class="mb-4 pa-3"
        variant="outlined"
      >
        <div class="text-caption text-medium-emphasis mb-2 d-flex align-center gap-1">
          <VIcon
            icon="ri-flashlight-line"
            size="16"
          />
          Quick links
        </div>
        <div class="d-flex flex-wrap gap-2">
          <VBtn
            size="small"
            variant="tonal"
            color="primary"
            prepend-icon="ri-qr-scan-2-line"
            :to="{ name: 'attendance-scanner' }"
          >
            Scanner
          </VBtn>
          <VBtn
            size="small"
            variant="tonal"
            prepend-icon="ri-calendar-check-line"
            :to="{ name: 'attendance-summaries' }"
          >
            Summaries
          </VBtn>
          <VBtn
            size="small"
            variant="tonal"
            prepend-icon="ri-wallet-3-line"
            :to="{ name: 'attendance-payroll' }"
          >
            Payroll
          </VBtn>
          <VBtn
            size="small"
            variant="tonal"
            prepend-icon="ri-map-pin-line"
            :to="{ name: 'attendance-locations' }"
          >
            Locations
          </VBtn>
        </div>
      </VCard>

      <VCard>
        <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
          <span class="d-flex align-center gap-2">
            <VIcon
              icon="ri-history-line"
              size="20"
            />
            Recent Activity Today
          </span>
          <span
            v-if="recentEventsCaption"
            class="text-caption text-medium-emphasis"
          >
            {{ recentEventsCaption }}
          </span>
        </VCardTitle>
        <div class="dashboard-table-scroll">
          <VTable
            class="dashboard-table"
            density="compact"
          >
            <thead>
              <tr>
                <th>
                  <span class="d-inline-flex align-center gap-1">
                    <VIcon
                      icon="ri-time-line"
                      size="14"
                    />
                    Time
                  </span>
                </th>
                <th>
                  <span class="d-inline-flex align-center gap-1">
                    <VIcon
                      icon="ri-user-line"
                      size="14"
                    />
                    Product
                  </span>
                </th>
                <th>
                  <span class="d-inline-flex align-center gap-1">
                    <VIcon
                      icon="ri-price-tag-3-line"
                      size="14"
                    />
                    Type
                  </span>
                </th>
                <th>
                  <span class="d-inline-flex align-center gap-1">
                    <VIcon
                      icon="ri-swap-line"
                      size="14"
                    />
                    Event
                  </span>
                </th>
                <th>
                  <span class="d-inline-flex align-center gap-1">
                    <VIcon
                      icon="ri-map-pin-line"
                      size="14"
                    />
                    Location
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="evt in recentEvents"
                :key="evt.id"
              >
                <td class="text-no-wrap">
                  {{ formatAttendanceTime(evt.recorded_at) }}
                </td>
                <td>{{ evt.product_name || evt.product_code || evt.product_id }}</td>
                <td>
                  <VChip
                    v-if="evt.product_type"
                    :color="evt.product_type === 'staff' ? 'info' : 'success'"
                    size="x-small"
                    label
                    :prepend-icon="evt.product_type === 'staff' ? 'ri-user-line' : 'ri-graduation-cap-line'"
                  >
                    {{ typeLabel(evt.product_type) }}
                  </VChip>
                  <span v-else>—</span>
                </td>
                <td>
                  <VChip
                    :color="eventColor(evt.event_type)"
                    size="small"
                    label
                    :prepend-icon="eventIcon(evt.event_type)"
                  >
                    {{ eventTypeLabel(evt.event_type) }}
                  </VChip>
                </td>
                <td>
                  <span class="d-inline-flex align-center gap-1">
                    <VIcon
                      v-if="evt.location"
                      icon="ri-map-pin-2-line"
                      size="14"
                      class="text-medium-emphasis"
                    />
                    {{ evt.location || '—' }}
                  </span>
                </td>
              </tr>
              <tr v-if="recentEvents.length === 0">
                <td
                  colspan="5"
                  class="text-center text-medium-emphasis py-8"
                >
                  <VIcon
                    icon="ri-inbox-line"
                    size="28"
                    class="mb-2 d-block mx-auto text-disabled"
                  />
                  No events today
                </td>
              </tr>
            </tbody>
          </VTable>
        </div>
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
        <VIcon
          icon="ri-checkbox-circle-line"
          size="28"
          color="success"
          class="mb-2 d-block mx-auto"
        />
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
                :prepend-icon="product.product_type === 'staff' ? 'ri-user-line' : 'ri-graduation-cap-line'"
              >
                {{ typeLabel(product.product_type) }}
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

<style scoped lang="scss">
.dashboard-table-scroll {
  overflow-x: auto;
}

.dashboard-table :deep(thead th),
.dashboard-table :deep(tbody td) {
  vertical-align: middle;
}
</style>
