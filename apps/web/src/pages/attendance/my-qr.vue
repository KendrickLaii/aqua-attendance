<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { getQRToken } from '@/api/attendance/events'
import type { QRPayload } from '@/api/attendance/events'

definePage({ meta: {} })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const qrData = ref<QRPayload | null>(null)
const countdown = ref(0)
const error = ref('')
const loading = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })
    return
  }
  await refreshQR()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function refreshQR() {
  loading.value = true
  error.value = ''
  try {
    qrData.value = await getQRToken()
    countdown.value = qrData.value.expires_in

    if (timer) clearInterval(timer)
    timer = setInterval(() => {
      if (countdown.value <= 0) {
        countdown.value = 0
        if (timer) clearInterval(timer)
        timer = null
        return
      }
      countdown.value--
    }, 1000)
  }
  catch (e: any) {
    error.value = e?.data?.detail || 'Failed to get QR code'
  }
  finally {
    loading.value = false
  }
}

const qrImageUrl = computed(() => {
  if (!qrData.value) return ''
  const encoded = encodeURIComponent(qrData.value.qr_token)
  return `https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=${encoded}`
})

const countdownColor = computed(() => {
  if (countdown.value > 30) return 'success'
  if (countdown.value > 10) return 'warning'
  return 'error'
})
</script>

<template>
  <VContainer class="d-flex flex-column align-center" style="max-width: 400px">
    <VCard class="w-100 text-center pa-6">
      <div class="text-h6 mb-2">
        {{ authStore.user?.full_name || authStore.user?.username }}
      </div>
      <VChip :color="authStore.role === 'student' ? 'success' : 'info'" size="small" label class="mb-4">
        {{ authStore.role }}
      </VChip>

      <div v-if="loading" class="py-12">
        <VProgressCircular indeterminate color="primary" size="48" />
      </div>

      <template v-else-if="qrData">
        <div class="mb-4 d-flex justify-center">
          <VImg
            :src="qrImageUrl"
            width="280"
            height="280"
            class="rounded"
            style="border: 4px solid rgb(var(--v-theme-primary))"
          />
        </div>

        <VProgressLinear
          :model-value="(countdown / (qrData.expires_in || 60)) * 100"
          :color="countdownColor"
          height="8"
          rounded
          class="mb-2"
        />
        <div class="text-body-2 text-medium-emphasis mb-4">
          Expires in <strong>{{ countdown }}s</strong>
        </div>

        <VBtn variant="outlined" size="small" @click="refreshQR">
          <VIcon icon="ri-refresh-line" class="me-1" />
          Refresh Now
        </VBtn>
      </template>

      <VAlert v-else-if="error" type="error" variant="tonal">
        {{ error }}
        <template #append>
          <VBtn size="small" variant="text" @click="refreshQR">
            Retry
          </VBtn>
        </template>
      </VAlert>
    </VCard>

    <div class="text-caption text-medium-emphasis text-center mt-4">
      Show this QR code to the scanner at the entrance.<br>
      Tap "Refresh Now" to generate a new QR code.
    </div>
  </VContainer>
</template>
