<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listProducts } from '@/api/attendance/products'
import type { Product } from '@/api/attendance/products'
import ProductQrDialogs from '@/components/attendance/ProductQrDialogs.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { openProductQrPrintPlaceholder, printProductQrs } from '@/utils/printProductQrs'

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
const selectedIds = ref<Set<string>>(new Set())
const printing = ref(false)
const printError = ref('')

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const productsCapped = computed(() => products.value.length >= PRODUCT_PAGE_SIZE)
const checkedInCount = computed(() => products.value.filter(p => p.attendance_status === 'checked_in').length)
const selectedCount = computed(() => selectedIds.value.size)

const allVisibleSelected = computed(() =>
  products.value.length > 0 && products.value.every(p => selectedIds.value.has(p.id)),
)

const selectedProducts = computed(() =>
  products.value.filter(p => selectedIds.value.has(p.id)),
)

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
    loadError.value = formatApiError(e, 'Failed to load products. Please try again.')
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

function isSelected(id: string) {
  return selectedIds.value.has(id)
}

function setSelected(id: string, value: boolean) {
  const next = new Set(selectedIds.value)
  if (value)
    next.add(id)
  else
    next.delete(id)
  selectedIds.value = next
}

function toggleSelectAllVisible() {
  if (allVisibleSelected.value) {
    selectedIds.value = new Set()

    return
  }
  selectedIds.value = new Set(products.value.map(p => p.id))
}

function clearSelection() {
  selectedIds.value = new Set()
}

function openQR(p: Product) {
  qrDialogsRef.value?.openQR(p)
}

async function printSelected() {
  if (!selectedProducts.value.length)
    return

  let printWindow: Window | null = null

  try {
    printWindow = openProductQrPrintPlaceholder()
  }
  catch (e) {
    printError.value = formatApiError(e, 'Could not open print window')

    return
  }

  printing.value = true
  printError.value = ''
  try {
    await printProductQrs(selectedProducts.value, printWindow)
  }
  catch (e) {
    printError.value = formatApiError(e, 'Could not print selected QR codes')
  }
  finally {
    printing.value = false
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
      <VCol
        cols="12"
        sm="5"
        class="d-flex flex-wrap align-center gap-2"
      >
        <VBtn
          variant="tonal"
          size="small"
          :prepend-icon="allVisibleSelected ? 'ri-checkbox-blank-line' : 'ri-checkbox-multiple-line'"
          :disabled="!products.length || loading"
          @click="toggleSelectAllVisible"
        >
          {{ allVisibleSelected ? 'Deselect all' : 'Select all' }}
        </VBtn>
        <VBtn
          v-if="selectedCount"
          variant="text"
          size="small"
          @click="clearSelection"
        >
          Clear ({{ selectedCount }})
        </VBtn>
        <VBtn
          color="primary"
          size="small"
          prepend-icon="ri-printer-line"
          :disabled="!selectedCount"
          :loading="printing"
          @click="printSelected"
        >
          Print selected{{ selectedCount ? ` (${selectedCount})` : '' }}
        </VBtn>
      </VCol>
      <VCol
        v-if="listCaption"
        cols="auto"
        class="ms-sm-auto"
      >
        <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
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

    <VAlert
      v-if="printError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="printError = ''"
    >
      {{ printError }}
    </VAlert>

    <VRow v-if="loading && !refreshing">
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

    <div
      v-else-if="products.length === 0 && !loadError"
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

    <VRow v-else-if="!loadError">
      <VCol
        v-for="p in products"
        :key="p.id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <ProductQrCard
          :product="p"
          :selected="isSelected(p.id)"
          @update:selected="setSelected(p.id, $event)"
          @open-detail="openQR(p)"
        />
      </VCol>
    </VRow>

    <ProductQrDialogs
      ref="qrDialogsRef"
      @rotated="loadProducts(true)"
    />
  </VContainer>
</template>
