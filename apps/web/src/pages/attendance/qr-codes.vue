<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listProducts } from '@/api/attendance/products'
import type { Product } from '@/api/attendance/products'
import ProductQrDialogs from '@/components/attendance/ProductQrDialogs.vue'
import { formatLastAttendance } from '@/utils/attendanceDisplay'

definePage({ meta: {} })

const PRODUCT_PAGE_SIZE = 200
const SEARCH_DEBOUNCE_MS = 300

const authStore = useAttendanceAuthStore()
const router = useRouter()

const products = ref<Product[]>([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
const filterType = ref('')
const searchQuery = ref('')
const qrDialogsRef = ref<InstanceType<typeof ProductQrDialogs> | null>(null)

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const productsCapped = computed(() => products.value.length >= PRODUCT_PAGE_SIZE)
const checkedInCount = computed(() => products.value.filter(p => p.attendance_status === 'checked_in').length)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = products.value.length
  const countLabel = productsCapped.value ? `${PRODUCT_PAGE_SIZE}+` : String(total)

  return `${countLabel} active · ${checkedInCount.value} checked in`
})

const listCaption = computed(() => {
  if (loading.value || products.value.length === 0)
    return ''

  const total = products.value.length
  if (productsCapped.value)
    return `Showing ${total} of ${PRODUCT_PAGE_SIZE}+ active products`
  if (searchQuery.value || filterType.value)
    return `Showing ${total} matching active product${total === 1 ? '' : 's'}`

  return `${total} active product${total === 1 ? '' : 's'}`
})

const emptyStateMessage = computed(() => {
  if (searchQuery.value || filterType.value)
    return 'No matching active products'

  return 'No active products found'
})

const showEmptyProductsCta = computed(() =>
  !searchQuery.value && !filterType.value,
)

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (!authStore.isAdmin) {
    router.replace({ name: 'attendance-dashboard' })

    return
  }
  await loadProducts()
})

async function loadProducts(isRefresh = false) {
  const softRefresh = isRefresh === true

  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    products.value = await listProducts({
      search: searchQuery.value || undefined,
      product_type: filterType.value || undefined,
      is_active: true,
      page_size: PRODUCT_PAGE_SIZE,
    })
  }
  catch (e) {
    console.error('Failed to load QR products', e)
    loadError.value = 'Failed to load products. Please try again.'
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadProducts = useDebounceFn(() => loadProducts(true), SEARCH_DEBOUNCE_MS)

watch(searchQuery, () => {
  debouncedLoadProducts()
})

watch(filterType, () => {
  loadProducts(true)
})

function openQR(p: Product) {
  qrDialogsRef.value?.openQR(p)
}

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function typeLabel(type: string) {
  return typeOptions.find(o => o.value === type)?.title ?? type
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
          QR Codes
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
          variant="outlined"
          color="primary"
          prepend-icon="ri-group-line"
          :to="{ name: 'attendance-products' }"
        >
          Manage products
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          @click="loadProducts(true)"
        >
          Refresh
        </VBtn>
      </VCol>
    </VRow>

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
          placeholder="Search products..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
        />
      </VCol>
      <VCol
        cols="12"
        sm="3"
      >
        <VSelect
          v-model="filterType"
          :items="[{ title: 'All Types', value: '' }, ...typeOptions]"
          label="Type"
          density="compact"
          hide-details
        />
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
          @click="loadProducts(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VCard :loading="loading">
      <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
        <span>Active products</span>
        <span
          v-if="listCaption"
          class="text-caption text-medium-emphasis"
        >
          {{ listCaption }}
        </span>
      </VCardTitle>

      <VCardText class="pa-4">
        <div
          v-if="!loading && products.length === 0 && !loadError"
          class="text-center text-medium-emphasis py-12"
        >
          <div class="mb-3">
            {{ emptyStateMessage }}
          </div>
          <VBtn
            v-if="showEmptyProductsCta"
            color="primary"
            prepend-icon="ri-group-line"
            :to="{ name: 'attendance-products' }"
          >
            Go to Product Management
          </VBtn>
        </div>

        <VRow v-else-if="!loading">
          <VCol
            v-for="p in products"
            :key="p.id"
            cols="12"
            sm="6"
            md="4"
            lg="3"
          >
            <VCard
              class="qr-product-card text-center"
              hover
              tabindex="0"
              role="button"
              :aria-label="`View QR code for ${p.full_name}`"
              @click="openQR(p)"
              @keydown.enter="openQR(p)"
              @keydown.space.prevent="openQR(p)"
            >
              <VCardText>
                <VIcon
                  icon="ri-qr-code-line"
                  size="48"
                  color="primary"
                  class="mb-2"
                />
                <div
                  class="qr-product-name text-subtitle-1 font-weight-bold"
                  :title="p.full_name"
                >
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
                    {{ typeLabel(p.product_type) }}
                  </VChip>
                </div>
                <div
                  class="text-caption mt-2"
                  :class="p.last_event_at && p.attendance_status === 'checked_in' ? 'text-success' : 'text-medium-emphasis'"
                >
                  {{ formatLastAttendance(p, { compact: true }) }}
                </div>
                <div class="text-caption text-disabled mt-2">
                  Tap to view QR
                </div>
              </VCardText>
            </VCard>
          </VCol>
        </VRow>
      </VCardText>
    </VCard>

    <ProductQrDialogs
      ref="qrDialogsRef"
      @rotated="loadProducts(true)"
    />
  </VContainer>
</template>

<style scoped lang="scss">
.qr-product-card {
  cursor: pointer;

  &:focus-visible {
    outline: 2px solid rgb(var(--v-theme-primary));
    outline-offset: 2px;
  }
}

.qr-product-name {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}
</style>
