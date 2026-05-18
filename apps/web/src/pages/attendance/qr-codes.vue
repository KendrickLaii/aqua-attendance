<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listProducts } from '@/api/attendance/products'
import { getQRToken } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'

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

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) { router.replace({ name: 'attendance-login' }); return }
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

async function refreshQR() {
  if (!qrProduct.value) return
  await openQR(qrProduct.value)
}

const qrImageUrl = computed(() => {
  if (!qrToken.value) return ''
  return `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(qrToken.value)}`
})

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
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
            <div class="text-subtitle-1 font-weight-bold">{{ p.full_name }}</div>
            <div class="text-body-2 text-medium-emphasis mb-2">{{ p.code }}</div>
            <VChip :color="typeColor(p.product_type)" size="small" label>
              {{ p.product_type }}
            </VChip>
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
        <VCardTitle class="text-h6">{{ qrProduct?.full_name }}</VCardTitle>
        <VCardSubtitle>{{ qrProduct?.code }} · {{ qrProduct?.product_type }}</VCardSubtitle>

        <div v-if="qrLoading" class="py-12">
          <VProgressCircular indeterminate color="primary" size="48" />
        </div>
        <template v-else-if="qrToken">
          <div class="my-4 d-flex justify-center">
            <VImg
              :src="qrImageUrl"
              width="300"
              height="300"
              class="rounded"
              style="border: 4px solid rgb(var(--v-theme-primary))"
            />
          </div>
          <div class="text-caption text-medium-emphasis mb-3">
            QR code expires in 60 seconds. Tap refresh to generate a new one.
          </div>
          <VBtn variant="outlined" size="small" @click="refreshQR" prepend-icon="ri-refresh-line">
            Refresh QR
          </VBtn>
        </template>
        <VAlert v-else type="error" variant="tonal" class="mt-4">
          Failed to generate QR code
        </VAlert>

        <VCardActions class="justify-center mt-2">
          <VBtn @click="qrDialog = false">Close</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
