<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listProducts } from '@/api/attendance/products'
import { getQRToken, refreshQRToken } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'
import { copyToClipboard } from '@/utils/copyToClipboard'
import { useQrImageUrl } from '@/composables/useQrImageUrl'

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
const qrLoading = ref(false)
const rotateConfirmOpen = ref(false)
const rotating = ref(false)

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
  qrDialog.value = true
  try {
    const data = await getQRToken(p.id)

    qrToken.value = data.qr_token
  }
  catch {
    qrToken.value = ''
  }
  finally {
    qrLoading.value = false
  }
}

async function confirmRotate() {
  if (!qrProduct.value) return
  rotating.value = true
  try {
    const data = await refreshQRToken(qrProduct.value.id)

    qrToken.value = data.qr_token
    qrProduct.value = { ...qrProduct.value, qr_token_version: data.token_version }
    rotateConfirmOpen.value = false
    await loadProducts()
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

const { qrImageUrl, qrImageError, qrImageLoading } = useQrImageUrl(qrToken, 300)

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function statusChip(p: Product) {
  return p.attendance_status === 'checked_in'
    ? { color: 'success', label: 'In', icon: 'ri-login-box-line' }
    : { color: 'grey', label: 'Out', icon: 'ri-logout-box-line' }
}
</script>

<template>
  <VContainer>
    <VRow class="mb-4" align="center">
      <VCol cols="12" sm="4">
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
      <VCol cols="12" sm="3">
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
      <VCol cols="12" class="text-center py-12">
        <VProgressCircular indeterminate color="primary" size="48" />
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
        <VCard class="text-center" hover @click="openQR(p)">
          <VCardText>
            <VIcon icon="ri-qr-code-line" size="48" color="primary" class="mb-2" />
            <div class="text-subtitle-1 font-weight-bold">
              {{ p.full_name }}
            </div>
            <div class="text-body-2 text-medium-emphasis mb-2">
              {{ p.code }}
            </div>
            <div class="d-flex justify-center gap-2">
              <VChip :color="typeColor(p.product_type)" size="small" label>
                {{ p.product_type }}
              </VChip>
              <VChip :color="statusChip(p).color" size="small" label :prepend-icon="statusChip(p).icon">
                {{ statusChip(p).label }}
              </VChip>
            </div>
          </VCardText>
        </VCard>
      </VCol>

      <VCol v-if="products.length === 0" cols="12">
        <VCard>
          <VCardText class="text-center text-medium-emphasis py-12">
            No active products found
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <!-- QR Code Dialog -->
    <VDialog v-model="qrDialog" max-width="420">
      <VCard class="text-center pa-6">
        <VCardTitle class="text-h6">
          {{ qrProduct?.full_name }}
        </VCardTitle>
        <VCardSubtitle>{{ qrProduct?.code }} · {{ qrProduct?.product_type }}</VCardSubtitle>

        <div v-if="qrLoading" class="py-12">
          <VProgressCircular indeterminate color="primary" size="48" />
        </div>
        <template v-else-if="qrToken">
          <div class="my-4 d-flex justify-center align-center" style="min-height: 300px">
            <VProgressCircular v-if="qrImageLoading" indeterminate color="primary" size="40" />
            <VAlert v-else-if="qrImageError" type="error" variant="tonal" density="compact">
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
            This QR stays valid — scan it again to toggle check-in / check-out.
            Paste the token on the
            <RouterLink :to="{ name: 'attendance-scanner' }" class="text-primary">
              web scanner
            </RouterLink>
            to test.
          </div>
          <div class="d-flex justify-center flex-wrap gap-2 mb-2">
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
              @click="rotateConfirmOpen = true"
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
        <VAlert v-else type="error" variant="tonal" class="mt-4">
          Failed to generate QR code
        </VAlert>

        <VCardActions class="justify-center mt-2">
          <VBtn @click="qrDialog = false">
            Close
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- Rotate confirmation -->
    <VDialog v-model="rotateConfirmOpen" max-width="420" persistent>
      <VCard>
        <VCardTitle>Rotate QR for {{ qrProduct?.full_name }}?</VCardTitle>
        <VCardText>
          The current QR will stop working. Use this only if the printed
          code was lost or shared with someone who shouldn't have it.
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="rotateConfirmOpen = false">
            Cancel
          </VBtn>
          <VBtn color="warning" :loading="rotating" @click="confirmRotate">
            Rotate
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VSnackbar v-model="copyFailOpen" color="error" location="bottom" :timeout="7000">
      Could not copy automatically. Select the text in the field above and copy manually (Ctrl+C or long-press).
    </VSnackbar>
  </VContainer>
</template>
