<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { scanQR } from '@/api/attendance/events'
import type { AttendanceEvent } from '@/api/attendance/events'

definePage({ meta: {} })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const manualInput = ref('')
const scanning = ref(false)
const result = ref<AttendanceEvent | null>(null)
const error = ref('')
const showResult = ref(false)

onMounted(() => {
  authStore.restoreSession()
  if (!authStore.isStaffOrAdmin) {
    router.replace({ name: 'attendance-login' })
  }
})

async function handleScan(qrToken?: string) {
  const token = qrToken || manualInput.value.trim()
  if (!token) return

  scanning.value = true
  error.value = ''
  result.value = null

  try {
    const evt = await scanQR({ qr_token: token, device_id: 'web-scanner' })
    result.value = evt
    showResult.value = true
    manualInput.value = ''
  }
  catch (e: any) {
    error.value = e?.data?.detail || 'Scan failed — QR may be expired or invalid.'
    showResult.value = true
  }
  finally {
    scanning.value = false
  }
}

function eventColor(type: string) {
  if (type === 'check_in') return 'success'
  if (type === 'check_out') return 'warning'
  return 'info'
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function resetResult() {
  showResult.value = false
  result.value = null
  error.value = ''
}
</script>

<template>
  <VContainer class="d-flex flex-column align-center" style="max-width: 600px">
    <VCard class="mb-6 w-100" variant="outlined">
      <VCardText class="text-center py-12">
        <VIcon icon="ri-camera-line" size="64" color="grey" class="mb-4" />
        <div class="text-body-1 text-medium-emphasis mb-2">
          Camera scanner available in mobile app
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Paste a QR token below to scan via web
        </div>
      </VCardText>
    </VCard>

    <VCard class="w-100 mb-6">
      <VCardTitle>Manual Token Input</VCardTitle>
      <VCardText>
        <VForm @submit.prevent="handleScan()">
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

    <VDialog v-model="showResult" max-width="400" persistent>
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
              {{ result.full_name || result.username }}
            </div>
            <div class="text-body-2 text-medium-emphasis">
              {{ formatTime(result.recorded_at) }}
            </div>
          </VCardText>
        </template>
        <template v-else-if="error">
          <VCardText class="text-center pa-8">
            <VIcon icon="ri-error-warning-line" color="error" size="80" class="mb-4" />
            <div class="text-h6 mb-2">Scan Failed</div>
            <div class="text-body-1 text-medium-emphasis">{{ error }}</div>
          </VCardText>
        </template>
        <VCardActions class="justify-center pb-4">
          <VBtn color="primary" variant="elevated" size="large" @click="resetResult">
            OK — Next Scan
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
