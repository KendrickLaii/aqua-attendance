<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listProducts } from '@/api/attendance/products'
import { getQRToken, refreshQRToken } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'
import { copyToClipboard } from '@/utils/copyToClipboard'
import { useQrImageUrl } from '@/composables/useQrImageUrl'
import { formatLastAttendance } from '@/utils/attendanceDisplay'

definePage({ meta: {} })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const products = ref<Product[]>([])
const loading = ref(true)
const filterType = ref('')
const searchQuery = ref('')

const qrDialog = ref(false)
const qrProduct = ref<Product | null>(null)
const qrToken = ref('')
const qrError = ref('')
const qrLoading = ref(false)
const rotateConfirmOpen = ref(false)
const rotating = ref(false)
const rotateError = ref('')

function openRotateConfirm() {
  rotateError.value = ''
  rotateConfirmOpen.value = true
}

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  await loadProducts()
})

async function loadProducts() {
  loading.value = true
  try {
    products.value = await listProducts({
      search: searchQuery.value || undefined,
      product_type: filterType.value || undefined,
      is_active: true,
    })
  }
  finally {
    loading.value = false
  }
}

async function openQR(p: Product) {
  qrProduct.value = p
  qrLoading.value = true
  qrToken.value = ''
  qrError.value = ''
  qrDialog.value = true
  try {
    const data = await getQRToken(p.id)

    qrToken.value = data.qr_token
  }
  catch (e: any) {
    qrToken.value = ''
    qrError.value = e?.data?.detail || 'Failed to load QR token'
  }
  finally {
    qrLoading.value = false
  }
}

async function confirmRotate() {
  if (!qrProduct.value)
    return
  rotating.value = true
  rotateError.value = ''
  try {
    const data = await refreshQRToken(qrProduct.value.id)

    qrToken.value = data.qr_token
    qrProduct.value = { ...qrProduct.value, qr_token_version: data.token_version }
    rotateConfirmOpen.value = false
    await loadProducts()
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined
    const detail = data?.detail

    rotateError.value = typeof detail === 'string' ? detail : 'Could not rotate QR code'
  }
  finally {
    rotating.value = false
  }
}

const copied = ref(false)
const copyFailOpen = ref(false)
let copiedHideTimer: ReturnType<typeof setTimeout> | null = null

async function copyQrToken() {
  if (!qrToken.value)
    return
  const ok = await copyToClipboard(qrToken.value)
  if (ok) {
    copyFailOpen.value = false
    copied.value = true
    if (copiedHideTimer)
      clearTimeout(copiedHideTimer)
    copiedHideTimer = setTimeout(() => {
      copied.value = false
    }, 2500)
  }
  else {
    copied.value = false
    copyFailOpen.value = true
  }
}

function selectTokenField(ev: FocusEvent) {
  const el = ev.target as HTMLInputElement | null

  el?.select()
}

const SCAN_TOKEN_SESSION_KEY = 'attendance-scan-token'

function openWebScanner() {
  if (qrToken.value && typeof sessionStorage !== 'undefined')
    sessionStorage.setItem(SCAN_TOKEN_SESSION_KEY, qrToken.value)
  qrDialog.value = false
  router.push({ name: 'attendance-scanner' })
}

const { qrImageUrl, qrImageError, qrImageLoading } = useQrImageUrl(qrToken, 300)

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="4"
      >
        <VTextField
          v-model="searchQuery"
          placeholder="Search..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          @update:model-value="loadProducts"
        />
      </VCol>
      <VCol
        cols="12"
        sm="3"
      >
        <VSelect
          v-model="filterType"
          :items="[{ title: 'All Types', value: '' }, { title: 'Staff', value: 'staff' }, { title: 'Student', value: 'student' }]"
          label="Type"
          density="compact"
          hide-details
          @update:model-value="loadProducts"
        />
      </VCol>
    </VRow>

    <VRow v-if="loading">
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

    <VRow v-else>
      <VCol
        v-for="p in products"
        :key="p.id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <VCard
          class="text-center"
          hover
          @click="openQR(p)"
        >
          <VCardText>
            <VIcon
              icon="ri-qr-code-line"
              size="48"
              color="primary"
              class="mb-2"
            />
            <div class="text-subtitle-1 font-weight-bold">
              {{ p.full_name }}
            </div>
            <div class="text-body-2 text-medium-emphasis mb-2">
              {{ p.code }}
            </div>
            <div class="d-flex justify-center gap-2 mb-2">
              <VChip
                :color="typeColor(p.product_type)"
                size="small"
                label
              >
                {{ p.product_type }}
              </VChip>
            </div>
            <div
              class="text-caption mt-2"
              :class="p.last_event_at && p.attendance_status === 'checked_in' ? 'text-success' : 'text-medium-emphasis'"
            >
              {{ formatLastAttendance(p) }}
            </div>
          </VCardText>
        </VCard>
      </VCol>

      <VCol
        v-if="products.length === 0"
        cols="12"
      >
        <VCard>
          <VCardText class="text-center text-medium-emphasis py-12">
            No active products found
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <!-- QR Code Dialog -->
    <VDialog
      v-model="qrDialog"
      max-width="420"
    >
      <VCard class="text-center pa-6">
        <VCardTitle class="text-h6">
          {{ qrProduct?.full_name }}
        </VCardTitle>
        <VCardSubtitle>{{ qrProduct?.code }} · {{ qrProduct?.product_type }}</VCardSubtitle>

        <div
          v-if="qrLoading"
          class="py-12"
        >
          <VProgressCircular
            indeterminate
            color="primary"
            size="48"
          />
        </div>
        <template v-else-if="qrToken">
          <div
            class="my-4 d-flex justify-center align-center"
            style="min-height: 300px"
          >
            <VProgressCircular
              v-if="qrImageLoading"
              indeterminate
              color="primary"
              size="40"
            />
            <VAlert
              v-else-if="qrImageError"
              type="error"
              variant="tonal"
              density="compact"
            >
              Could not render QR image.
            </VAlert>
            <VImg
              v-else-if="qrImageUrl"
              :src="qrImageUrl"
              width="300"
              height="300"
              class="rounded"
              style="border: 4px solid rgb(var(--v-theme-primary))"
            />
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            This QR stays valid until you rotate it. On scan, choose Check In or Check Out
            (mobile app or web scanner). Same code works every day.
          </div>
          <div class="d-flex justify-center flex-wrap gap-2 mb-2">
            <VBtn
              variant="tonal"
              size="small"
              color="primary"
              prepend-icon="ri-qr-scan-2-line"
              @click="openWebScanner"
            >
              Web scanner
            </VBtn>
            <VBtn
              variant="outlined"
              size="small"
              :prepend-icon="copied ? 'ri-check-line' : 'ri-file-copy-line'"
              :color="copied ? 'success' : undefined"
              @click="copyQrToken"
            >
              {{ copied ? 'Copied' : 'Copy token' }}
            </VBtn>
            <VBtn
              variant="text"
              size="small"
              color="warning"
              prepend-icon="ri-refresh-line"
              @click="openRotateConfirm"
            >
              Rotate QR
            </VBtn>
          </div>
          <VTextField
            :model-value="qrToken"
            readonly
            label="Raw token (tap to select, then copy)"
            density="compact"
            variant="outlined"
            class="text-start mt-4"
            hide-details
            @focus="selectTokenField"
          />
          <div class="text-caption text-disabled mt-2">
            Token version: {{ qrProduct?.qr_token_version }}
          </div>
        </template>
        <VAlert
          v-else
          type="error"
          variant="tonal"
          class="mt-4"
        >
          {{ qrError || 'Failed to generate QR code' }}
        </VAlert>

        <VCardActions class="justify-center mt-2">
          <VBtn @click="qrDialog = false">
            Close
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- Rotate confirmation -->
    <VDialog
      v-model="rotateConfirmOpen"
      max-width="420"
      persistent
    >
      <VCard>
        <VCardTitle>Rotate QR for {{ qrProduct?.full_name }}?</VCardTitle>
        <VCardText>
          <VAlert
            v-if="rotateError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
            closable
            @click:close="rotateError = ''"
          >
            {{ rotateError }}
          </VAlert>
          The current QR will stop working. Use this only if the printed
          code was lost or shared with someone who shouldn't have it.
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="rotateConfirmOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="warning"
            :loading="rotating"
            @click="confirmRotate"
          >
            Rotate
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VSnackbar
      v-model="copyFailOpen"
      color="error"
      location="bottom"
      :timeout="7000"
    >
      Could not copy automatically. Select the text in the field above and copy manually (Ctrl+C or long-press).
    </VSnackbar>
  </VContainer>
</template>
