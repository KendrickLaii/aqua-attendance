<script setup lang="ts">
import type { Shift, ShiftTemplate } from '@/api/attendance/shifts'
import {
  type StaffLocation,
  type StaffShiftMe,
  type StaffShiftRequest,
  cancelStaffShiftRequest,
  createStaffShiftRequest,
  fetchStaffLocations,
  fetchStaffMe,
  fetchStaffTemplates,
  fetchStaffWeek,
  loginStaffShift,
  logoutStaffShift,
  useStaffShiftToken,
} from '@/api/attendance/staffShifts'
import { formatApiError } from '@/utils/formatApiDetail'
import {
  STAFF_SHIFT_LOGIN_HINT,
  STAFF_SHIFT_REJECTED_HINT,
  STAFF_SHIFT_REQUEST_DAY_HINT,
  STAFF_SHIFT_REQUEST_DIALOG_HINT,
  STAFF_SHIFT_WEEK_HINT,
} from '@/utils/shiftStaffCopy'
import {
  addDays,
  formatDayHeader,
  formatWeekRange,
  hhmm,
  isWeekend,
  mondayOf,
  readableTextColor,
  toIsoDate,
  weekDates,
} from '@/utils/shiftDisplay'

definePage({
  meta: {
    public: true,
    layout: 'blank',
  },
})

const token = useStaffShiftToken()
const me = ref<StaffShiftMe | null>(null)
const loginForm = reactive({ code: '', pin: '' })
const showPin = ref(false)
const loginError = ref('')
const loginBusy = ref(false)

const weekStart = ref(mondayOf(new Date()))
const today = toIsoDate(new Date())
const dates = computed(() => weekDates(weekStart.value))
const shifts = ref<Shift[]>([])
const requests = ref<StaffShiftRequest[]>([])
const templates = ref<ShiftTemplate[]>([])
const locations = ref<StaffLocation[]>([])
const loadError = ref('')
const pageBusy = ref(false)

const requestOpen = ref(false)
const requestDate = ref('')
const requestBusy = ref(false)
const requestError = ref('')
const requestForm = reactive({
  location_id: '',
  template_id: '' as string,
  start_time: '09:00',
  end_time: '13:00',
  title: '',
  color: '#1565C0',
})

function locationOf(id: string) {
  return locations.value.find(l => l.id === id)
}

function locationShort(id: string) {
  const loc = locationOf(id)

  return loc?.name_en || loc?.name_zh || ''
}

function locationFull(id: string) {
  const loc = locationOf(id)

  return loc ? [loc.name_en, loc.name_zh].filter(Boolean).join(' · ') : ''
}

const pendingCount = computed(() => requests.value.filter(r => r.status === 'pending').length)

function itemsOn(date: string) {
  return {
    shifts: shifts.value.filter(s => s.shift_date === date),
    pending: requests.value.filter(r => r.shift_date === date && r.status === 'pending'),
    rejected: requests.value.filter(r => r.shift_date === date && r.status === 'rejected'),
  }
}

async function loadWeek() {
  pageBusy.value = true
  loadError.value = ''
  try {
    const [week, templateList, locationList] = await Promise.all([
      fetchStaffWeek(weekStart.value, addDays(weekStart.value, 6)),
      fetchStaffTemplates(),
      fetchStaffLocations(),
    ])

    shifts.value = week.shifts
    requests.value = week.requests
    templates.value = templateList
    locations.value = locationList
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not load your shifts.')
    const status = e && typeof e === 'object' && 'statusCode' in e ? (e as { statusCode?: number }).statusCode : undefined
    if (status === 401) {
      token.value = null
      me.value = null
    }
  }
  finally {
    pageBusy.value = false
  }
}

async function restoreSession() {
  if (!token.value)
    return
  try {
    me.value = await fetchStaffMe()
    await loadWeek()
  }
  catch {
    token.value = null
    me.value = null
  }
}

onMounted(restoreSession)

async function handleLogin() {
  loginBusy.value = true
  loginError.value = ''
  try {
    me.value = await loginStaffShift(loginForm.code.trim(), loginForm.pin.trim())
    await loadWeek()
  }
  catch (e) {
    loginError.value = formatApiError(e, 'Login failed. Check your staff code and PIN.')
  }
  finally {
    loginBusy.value = false
  }
}

async function handleLogout() {
  await logoutStaffShift()
  me.value = null
  shifts.value = []
  requests.value = []
}

function openRequest(date: string) {
  if (date < today)
    return
  requestDate.value = date
  requestError.value = ''
  requestForm.location_id = locations.value[0]?.id ?? ''
  const template = templates.value[0]

  requestForm.template_id = template?.id ?? ''
  requestForm.start_time = template ? hhmm(template.start_time) : '09:00'
  requestForm.end_time = template ? hhmm(template.end_time) : '13:00'
  requestForm.title = template?.name ?? ''
  requestForm.color = template?.color ?? '#1565C0'
  requestOpen.value = true
}

function applyTemplate(template: ShiftTemplate) {
  requestForm.template_id = template.id
  requestForm.start_time = hhmm(template.start_time)
  requestForm.end_time = hhmm(template.end_time)
  requestForm.title = template.name
  requestForm.color = template.color
}

async function submitRequest() {
  requestBusy.value = true
  requestError.value = ''
  try {
    await createStaffShiftRequest({
      location_id: requestForm.location_id,
      shift_date: requestDate.value,
      start_time: requestForm.start_time,
      end_time: requestForm.end_time,
      title: requestForm.title || null,
      color: requestForm.color,
      template_id: requestForm.template_id || null,
    })
    requestOpen.value = false
    await loadWeek()
  }
  catch (e) {
    requestError.value = formatApiError(e, 'Could not submit this shift.')
  }
  finally {
    requestBusy.value = false
  }
}

async function cancelRequest(id: string) {
  pageBusy.value = true
  try {
    await cancelStaffShiftRequest(id)
    await loadWeek()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not cancel this request.')
  }
  finally {
    pageBusy.value = false
  }
}
</script>

<template>
  <div
    class="d-flex justify-center pa-4"
    style="min-height: 100vh; background: rgb(var(--v-theme-background))"
  >
    <div style="width: 100%; max-width: 1180px">
      <div
        v-if="!me"
        class="d-flex align-center justify-center"
        style="min-height: calc(100vh - 32px)"
      >
        <VCard
          class="pa-6"
          max-width="440"
          width="100%"
        >
          <VCardTitle class="text-h5 text-center mb-2">
            <VIcon
              icon="ri-calendar-schedule-line"
              class="me-2"
            />
            My shifts
          </VCardTitle>
          <VCardSubtitle class="text-center mb-1">
            Sign in with your staff code and PIN
          </VCardSubtitle>
          <p class="text-caption text-medium-emphasis text-center mb-4">
            {{ STAFF_SHIFT_LOGIN_HINT }}
          </p>
          <VAlert
            v-if="loginError"
            type="error"
            variant="tonal"
            class="mb-4"
            closable
            @click:close="loginError = ''"
          >
            {{ loginError }}
          </VAlert>
          <VForm @submit.prevent="handleLogin">
            <VTextField
              v-model="loginForm.code"
              label="Staff code"
              prepend-inner-icon="ri-user-line"
              autocomplete="username"
              class="mb-3"
            />
            <VTextField
              v-model="loginForm.pin"
              label="PIN"
              :type="showPin ? 'text' : 'password'"
              prepend-inner-icon="ri-lock-line"
              inputmode="numeric"
              maxlength="6"
              autocomplete="current-password"
              class="mb-4"
            >
              <template #append-inner>
                <VIcon
                  :icon="showPin ? 'ri-eye-off-line' : 'ri-eye-line'"
                  style="cursor: pointer"
                  @click="showPin = !showPin"
                />
              </template>
            </VTextField>
            <VBtn
              type="submit"
              block
              color="primary"
              size="large"
              :loading="loginBusy"
            >
              Sign in
            </VBtn>
          </VForm>
        </VCard>
      </div>

      <template v-else>
        <div class="d-flex flex-wrap align-center gap-3 mb-4">
          <div class="me-auto">
            <div class="text-h5 font-weight-medium">
              {{ me.full_name }}
            </div>
            <div class="text-body-2 text-medium-emphasis">
              {{ me.code }} · {{ shifts.length }} confirmed · {{ pendingCount }} pending
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ STAFF_SHIFT_WEEK_HINT }}
            </div>
          </div>
          <VBtn
            variant="text"
            @click="handleLogout"
          >
            Sign out
          </VBtn>
        </div>

        <VAlert
          v-if="loadError"
          type="error"
          variant="tonal"
          class="mb-4"
          closable
          @click:close="loadError = ''"
        >
          {{ loadError }}
        </VAlert>

        <VCard>
          <div class="d-flex flex-wrap align-center gap-2 pa-3">
            <IconBtn
              aria-label="Previous week"
              @click="weekStart = addDays(weekStart, -7); loadWeek()"
            >
              <VIcon icon="ri-arrow-left-s-line" />
            </IconBtn>
            <div class="text-h6">
              {{ formatWeekRange(weekStart) }}
            </div>
            <IconBtn
              aria-label="Next week"
              @click="weekStart = addDays(weekStart, 7); loadWeek()"
            >
              <VIcon icon="ri-arrow-right-s-line" />
            </IconBtn>
            <VSpacer />
            <span class="text-caption text-medium-emphasis">
              <span class="legend-dot legend-dot-solid" />Confirmed
              <span class="text-medium-emphasis ms-1">已確認</span>
              <span class="legend-dot legend-dot-wait ms-3" />Pending
              <span class="text-medium-emphasis ms-1">待確認</span>
            </span>
            <VProgressCircular
              v-if="pageBusy"
              indeterminate
              size="20"
              width="2"
            />
          </div>
          <div class="week">
            <section
              v-for="date in dates"
              :key="date"
              class="day"
              :class="{ today: date === today, weekend: isWeekend(date) }"
            >
              <header class="day-head">
                <span>{{ formatDayHeader(date).weekday }}</span>
                <strong>{{ formatDayHeader(date).day }}</strong>
                <VChip
                  v-if="date === today"
                  size="x-small"
                  color="primary"
                  variant="tonal"
                >
                  Today
                </VChip>
              </header>

              <div
                v-for="shift in itemsOn(date).shifts"
                :key="shift.id"
                class="shift-block"
                :style="{ '--shift-bg': shift.color, color: readableTextColor(shift.color) }"
              >
                <span class="shift-time">{{ hhmm(shift.start_time) }}–{{ hhmm(shift.end_time) }}</span>
                <span
                  v-if="shift.title"
                  class="shift-title"
                >{{ shift.title }}</span>
                <span
                  class="shift-sub"
                  :title="locationFull(shift.location_id)"
                >{{ locationShort(shift.location_id) }}</span>
              </div>

              <div
                v-for="request in itemsOn(date).pending"
                :key="request.id"
                class="shift-block shift-pending"
                :style="{ '--shift-bg': request.color }"
              >
                <span class="shift-time">{{ hhmm(request.start_time) }}–{{ hhmm(request.end_time) }}</span>
                <span
                  v-if="request.title"
                  class="shift-title"
                >{{ request.title }}</span>
                <span
                  class="shift-sub"
                  :title="locationFull(request.location_id)"
                >{{ locationShort(request.location_id) }}</span>
                <span class="shift-sub">Pending</span>
                <VBtn
                  size="x-small"
                  variant="text"
                  color="error"
                  class="align-self-start px-0"
                  @click="cancelRequest(request.id)"
                >
                  Cancel
                </VBtn>
              </div>

              <p
                v-for="request in itemsOn(date).rejected"
                :key="request.id"
                class="rejected"
              >
                {{ hhmm(request.start_time) }}–{{ hhmm(request.end_time) }} {{ STAFF_SHIFT_REJECTED_HINT }}
                <template v-if="request.reject_reason">
                  · {{ request.reject_reason }}
                </template>
              </p>

              <VBtn
                v-if="date >= today"
                size="small"
                variant="text"
                class="mt-auto"
                prepend-icon="ri-add-line"
                @click="openRequest(date)"
              >
                Request
                <VTooltip
                  activator="parent"
                  location="top"
                >
                  {{ STAFF_SHIFT_REQUEST_DAY_HINT }}
                </VTooltip>
              </VBtn>
            </section>
          </div>
        </VCard>
      </template>
    </div>

    <VDialog
      v-model="requestOpen"
      max-width="520"
    >
      <VCard>
        <VCardTitle>
          Request a shift
          <template v-if="requestDate">
            · {{ formatDayHeader(requestDate).weekday }} {{ formatDayHeader(requestDate).day }}
          </template>
        </VCardTitle>
        <VCardSubtitle class="px-4 pb-2">
          {{ STAFF_SHIFT_REQUEST_DIALOG_HINT }}
        </VCardSubtitle>
        <VCardText>
          <VAlert
            v-if="requestError"
            type="error"
            variant="tonal"
            class="mb-3"
          >
            {{ requestError }}
          </VAlert>
          <div class="d-flex flex-wrap gap-2 mb-3">
            <VChip
              v-for="template in templates"
              :key="template.id"
              :color="requestForm.template_id === template.id ? 'primary' : undefined"
              :variant="requestForm.template_id === template.id ? 'flat' : 'tonal'"
              @click="applyTemplate(template)"
            >
              <span
                class="legend-dot me-2"
                :style="{ background: template.color }"
              />
              {{ template.name }} {{ hhmm(template.start_time) }}–{{ hhmm(template.end_time) }}
            </VChip>
          </div>
          <VSelect
            v-model="requestForm.location_id"
            :items="locations.map(l => ({ title: locationFull(l.id), value: l.id }))"
            label="Location"
          />
          <div class="d-flex gap-3 mt-2">
            <VTextField
              v-model="requestForm.start_time"
              label="Start"
              type="time"
            />
            <VTextField
              v-model="requestForm.end_time"
              label="End"
              type="time"
            />
          </div>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="requestOpen = false"
          >
            Close
          </VBtn>
          <VBtn
            color="primary"
            :loading="requestBusy"
            :disabled="!requestForm.location_id"
            @click="submitRequest"
          >
            Submit request
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.week {
  display: grid;
  grid-template-columns: repeat(7, minmax(140px, 1fr));
  gap: 8px;
  overflow-x: auto;
  padding: 0 12px 16px;
}

.day {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 180px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.03);
}

.day.weekend {
  background: rgba(var(--v-theme-on-surface), 0.018);
}

.day.today {
  background: rgba(var(--v-theme-primary), 0.05);
  box-shadow: inset 0 0 0 1px rgb(var(--v-theme-primary));
}

.day-head {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
  margin-bottom: 2px;
}

.day-head span {
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.shift-block {
  display: flex;
  flex-direction: column;
  border-radius: 6px;
  background: var(--shift-bg);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 12%);
  line-height: 1.25;
  padding-block: 5px;
  padding-inline: 8px;
}

.shift-time {
  font-size: 0.8rem;
  font-weight: 600;
}

.shift-title,
.shift-sub {
  overflow: hidden;
  font-size: 0.72rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shift-sub {
  opacity: 0.85;
}

.shift-pending {
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.28);
  border-left: 3px solid var(--shift-bg);
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
}

.rejected {
  margin: 0;
  color: rgb(var(--v-theme-error));
  font-size: 0.72rem;
  line-height: 1.35;
}

.legend-dot {
  display: inline-block;
  border-radius: 3px;
  block-size: 10px;
  inline-size: 10px;
  margin-inline-end: 6px;
  vertical-align: -1px;
}

.legend-dot-solid {
  background: rgb(var(--v-theme-primary));
}

.legend-dot-wait {
  border: 2px solid rgb(var(--v-theme-primary));
}

@media (max-width: 720px) {
  .week {
    grid-template-columns: 1fr;
  }
}
</style>
