<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { scanQR } from '@/api/attendance/events'
import type { AttendanceEvent } from '@/api/attendance/events'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const SCAN_LOCATION_KEY = 'attendance-scan-location-id'
const SCAN_EVENT_TYPE_KEY = 'attendance-scan-event-type'

function readStoredEventType(): 'check_in' | 'check_out' {
  if (typeof localStorage === 'undefined')
    return 'check_in'
  const stored = localStorage.getItem(SCAN_EVENT_TYPE_KEY)

  return stored === 'check_out' ? 'check_out' : 'check_in'
}

const manualInput = ref('')
const locations = ref<LocationItem[]>([])
const selectedEventType = ref<'check_in' | 'check_out'>(readStoredEventType())

const selectedLocationId = ref(
  typeof localStorage !== 'undefined'
    ? localStorage.getItem(SCAN_LOCATION_KEY) || ''
    : '',
)

const scanning = ref(false)
const result = ref<AttendanceEvent | null>(null)
const error = ref('')
const showResult = ref(false)
const tokenFromQrPage = ref(false)

const SCAN_TOKEN_SESSION_KEY = 'attendance-scan-token'

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (typeof sessionStorage !== 'undefined') {
    const pending = sessionStorage.getItem(SCAN_TOKEN_SESSION_KEY)
    if (pending) {
      manualInput.value = pending
      tokenFromQrPage.value = true
      sessionStorage.removeItem(SCAN_TOKEN_SESSION_KEY)
    }
  }
  try {
    locations.value = await listLocations({ is_active: true, page_size: 200 })
  }
  catch {}
})

async function handleScan(qrToken?: string) {
  const token = typeof qrToken === 'string' ? qrToken : manualInput.value.trim()
  if (!token)
    return

  scanning.value = true
  error.value = ''
  result.value = null

  try {
    const locationId = selectedLocationId.value || undefined
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(SCAN_LOCATION_KEY, selectedLocationId.value || '')
      localStorage.setItem(SCAN_EVENT_TYPE_KEY, selectedEventType.value)
    }

    const evt = await scanQR({
      qr_token: token,
      device_id: 'web-scanner',
      location_id: locationId,
      event_type: selectedEventType.value,
    })

    result.value = evt
    showResult.value = true
    manualInput.value = ''
    tokenFromQrPage.value = false
  }
  catch (e: unknown) {
    error.value = formatApiError(e, 'Scan failed — QR may be expired or invalid.')
    showResult.value = true
  }
  finally {
    scanning.value = false
  }
}

function eventColor(type: string) {
  if (type === 'check_in')
    return 'success'
  if (type === 'check_out')
    return 'warning'

  return 'info'
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function resetResult() {
  showResult.value = false
  result.value = null
  error.value = ''
}
</script>

<template>
  <VContainer
    class="d-flex flex-column align-center"
    style="max-width: 600px"
  >
    <VCard
      class="mb-6 w-100"
      variant="outlined"
    >
      <VCardText class="text-center py-12">
        <VIcon
          icon="ri-camera-line"
          size="64"
          color="grey"
          class="mb-4"
        />
        <div class="text-body-1 text-medium-emphasis mb-2">
          Camera scanner available in mobile app
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Paste a QR token below to scan via web
        </div>
      </VCardText>
    </VCard>

    <VAlert
      v-if="tokenFromQrPage"
      type="info"
      variant="tonal"
      density="compact"
      class="w-100 mb-4"
      icon="ri-information-line"
    >
      QR token loaded — choose Check In or Check Out, then press Process Scan.
    </VAlert>

    <VCard class="w-100 mb-6">
      <VCardTitle>Manual Token Input</VCardTitle>
      <VCardText>
        <VForm @submit.prevent="() => handleScan()">
          <div class="text-body-2 text-medium-emphasis mb-2">
            Action
          </div>
          <VBtnToggle
            v-model="selectedEventType"
            mandatory
            divided
            class="mb-3 d-flex w-100"
            color="primary"
          >
            <VBtn
              value="check_in"
              class="flex-grow-1"
            >
              Check In
            </VBtn>
            <VBtn
              value="check_out"
              class="flex-grow-1"
            >
              Check Out
            </VBtn>
          </VBtnToggle>
          <VSelect
            v-model="selectedLocationId"
            :items="locations.map(l => ({ title: `${l.name_zh}${l.name_en ? ` / ${l.name_en}` : ''}`, value: l.id }))"
            label="Scan location"
            prepend-inner-icon="ri-map-pin-line"
            hint="Select managed location for this check-in / check-out"
            persistent-hint
            clearable
            class="mb-3"
          />
          <VTextarea
            v-model="manualInput"
            label="QR Token"
            placeholder="Paste QR token value here..."
            rows="3"
            class="mb-3"
          />
          <VBtn
            type="submit"
            color="primary"
            block
            :loading="scanning"
            prepend-icon="ri-qr-scan-2-line"
          >
            Process Scan
          </VBtn>
        </VForm>
      </VCardText>
    </VCard>

    <VDialog
      v-model="showResult"
      max-width="400"
      persistent
    >
      <VCard>
        <template v-if="result">
          <VCardText class="text-center pa-8">
            <VIcon
              :icon="result.event_type === 'check_in' ? 'ri-login-box-line' : 'ri-logout-box-line'"
              :color="eventColor(result.event_type)"
              size="80"
              class="mb-4"
            />
            <div class="text-h5 mb-2">
              {{ result.event_type.replace('_', ' ').toUpperCase() }}
            </div>
            <div class="text-h6 mb-1">
              {{ result.product_name || result.product_code }}
            </div>
            <div class="text-caption text-medium-emphasis mb-2">
              {{ result.product_id }}
            </div>
            <div class="d-flex justify-center gap-2 mb-2">
              <VChip
                v-if="result.product_type"
                :color="result.product_type === 'staff' ? 'info' : 'success'"
                size="small"
                label
              >
                {{ result.product_type }}
              </VChip>
              <VChip
                v-if="result.attendance_status"
                :color="result.attendance_status === 'checked_in' ? 'success' : 'grey'"
                size="small"
                label
              >
                Now: {{ result.attendance_status === 'checked_in' ? 'IN' : 'OUT' }}
              </VChip>
            </div>
            <div class="text-body-2 text-medium-emphasis mb-1">
              {{ formatTime(result.recorded_at) }}
            </div>
            <div
              v-if="result.location"
              class="text-body-2"
            >
              <VIcon
                icon="ri-map-pin-line"
                size="16"
                class="me-1"
              />
              {{ result.location }}
            </div>
          </VCardText>
        </template>
        <template v-else-if="error">
          <VCardText class="text-center pa-8">
            <VIcon
              icon="ri-error-warning-line"
              color="error"
              size="80"
              class="mb-4"
            />
            <div class="text-h6 mb-2">
              Scan Failed
            </div>
            <div class="text-body-1 text-medium-emphasis">
              {{ error }}
            </div>
          </VCardText>
        </template>
        <VCardActions class="justify-center pb-4">
          <VBtn
            color="primary"
            variant="elevated"
            size="large"
            @click="resetResult"
          >
            OK — Next Scan
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
