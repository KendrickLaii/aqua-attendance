<script setup lang="ts">
import {
  type InventoryItem,
  type InventoryStock,
  exportInventoryStocksCSV,
  importOpeningStockCSV,
  listInventoryItems,
  listInventoryStocks,
} from '@/api/attendance/inventory'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import InventoryMovementDialog from '@/components/attendance/inventory/InventoryMovementDialog.vue'
import InventoryTransferDialog from '@/components/attendance/inventory/InventoryTransferDialog.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const locations = ref<LocationItem[]>([])
const items = ref<InventoryItem[]>([])
const stocks = ref<InventoryStock[]>([])

const selectedLocationId = ref<string | null>(null)
const search = ref('')
const movementDialogOpen = ref(false)
const transferDialogOpen = ref(false)
const openingStockInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)

const itemById = computed(() => new Map(items.value.map(i => [i.id, i])))

const rows = computed(() => {
  const term = search.value.trim().toLowerCase()

  return stocks.value
    .map(stock => {
      const item = itemById.value.get(stock.item_id)
      if (!item)
        return null
      if (
        term
        && ![item.sku_code, item.name_zh, item.name_en ?? '']
          .some(v => v.toLowerCase().includes(term))
      )
        return null

      return { stock, item, isLow: stock.quantity <= item.reorder_level }
    })
    .filter((r): r is NonNullable<typeof r> => r !== null)
    .sort((a, b) => a.item.sku_code.localeCompare(b.item.sku_code, undefined, { numeric: true }))
})

const statCards = computed(() => {
  const totalUnits = stocks.value.reduce((sum, s) => sum + s.quantity, 0)

  const lowCount = stocks.value.filter(
    s => s.quantity <= (itemById.value.get(s.item_id)?.reorder_level ?? -1),
  ).length

  return [
    { label: 'Tracked items', value: String(new Set(stocks.value.map(s => s.item_id)).size), icon: 'ri-archive-line', color: 'primary' },
    { label: 'Units on hand', value: String(totalUnits), icon: 'ri-stack-line', color: 'info' },
    { label: 'Low-stock items', value: String(lowCount), icon: 'ri-error-warning-line', color: lowCount > 0 ? 'error' : 'success' },
  ]
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()
})

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [locationList, itemList] = await Promise.all([
      listLocations({ is_active: true }),
      listInventoryItems(),
    ])

    locations.value = [...locationList].sort((a, b) => a.name_en.localeCompare(b.name_en))
    items.value = itemList
    if (!selectedLocationId.value && locationList.length > 0)
      selectedLocationId.value = locationList[0].id
    await loadStocks()
  }
  catch (e) {
    console.error('Failed to load inventory', e)
    loadError.value = formatApiError(e, 'Failed to load inventory.')
  }
  finally {
    loading.value = false
  }
}

async function loadStocks() {
  stocks.value = selectedLocationId.value
    ? await listInventoryStocks({ location_id: selectedLocationId.value })
    : await listInventoryStocks()
}

watch(selectedLocationId, async () => {
  try {
    await loadStocks()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load stock.')
  }
})

async function exportStocks() {
  try {
    const blob = await exportInventoryStocksCSV(
      selectedLocationId.value ? { location_id: selectedLocationId.value } : undefined,
    )

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = 'inventory_stocks.csv'
    link.click()
    URL.revokeObjectURL(url)
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Export failed.')
  }
}

function pickOpeningStockFile() {
  openingStockInput.value?.click()
}

async function onOpeningStockFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  input.value = ''
  if (!file)
    return
  importing.value = true
  try {
    const result = await importOpeningStockCSV(file)
    if (result.errors.length)
      loadError.value = result.errors.map(e => `Row ${e.row}: ${e.error}`).join(' ')
    await loadStocks()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Opening stock import failed.')
  }
  finally {
    importing.value = false
  }
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <div class="text-h5 font-weight-medium">
          Inventory 庫存管理
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadAll"
        >
          Refresh
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-download-line"
          @click="exportStocks"
        >
          Export CSV
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-upload-line"
          :loading="importing"
          @click="pickOpeningStockFile"
        >
          Import Opening Stock
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-swap-line"
          :disabled="!selectedLocationId"
          @click="transferDialogOpen = true"
        >
          Transfer
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          :disabled="!selectedLocationId"
          @click="movementDialogOpen = true"
        >
          Record Movement
        </VBtn>
        <input
          ref="openingStockInput"
          type="file"
          accept=".csv,text/csv"
          class="d-none"
          @change="onOpeningStockFile"
        >
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
    </VAlert>

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

    <template v-else>
      <StatCards :cards="statCards" />

      <VCard>
        <VCardText class="d-flex flex-wrap gap-3 align-center">
          <VSelect
            v-model="selectedLocationId"
            :items="locations.map(l => ({ value: l.id, title: [l.name_en, l.name_zh].filter(Boolean).join(' · ') }))"
            label="Location"
            density="comfortable"
            style="max-width: 280px"
            hide-details
          />
          <VTextField
            v-model="search"
            label="Search item"
            prepend-inner-icon="ri-search-line"
            density="comfortable"
            style="max-width: 320px"
            hide-details
            clearable
          />
        </VCardText>
        <VTable>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Item</th>
              <th>Unit</th>
              <th class="text-end">
                On hand
              </th>
              <th class="text-end">
                Reserved
              </th>
              <th class="text-end">
                Available
              </th>
              <th class="text-end">
                Reorder level
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.stock.id"
              :class="row.isLow ? 'text-error' : undefined"
            >
              <td>{{ row.item.sku_code }}</td>
              <td>{{ [row.item.name_zh, row.item.name_en].filter(Boolean).join(' · ') }}</td>
              <td>{{ row.item.unit_of_measure || '—' }}</td>
              <td class="text-end font-weight-medium">
                {{ row.stock.quantity }}
              </td>
              <td class="text-end">
                {{ row.stock.reserved }}
              </td>
              <td class="text-end">
                {{ row.stock.available }}
              </td>
              <td class="text-end">
                {{ row.item.reorder_level }}
              </td>
              <td>
                <VChip
                  :color="row.isLow ? 'error' : 'success'"
                  size="small"
                  variant="tonal"
                >
                  {{ row.isLow ? 'Low stock' : 'OK' }}
                </VChip>
              </td>
            </tr>
            <tr v-if="rows.length === 0">
              <td
                colspan="8"
                class="text-center text-medium-emphasis py-8"
              >
                No stock records for this location yet. Use “Record Movement” to add stock.
              </td>
            </tr>
          </tbody>
        </VTable>
      </VCard>
    </template>

    <InventoryMovementDialog
      v-model="movementDialogOpen"
      :location-id="selectedLocationId"
      :items="items"
      @saved="loadStocks"
    />
    <InventoryTransferDialog
      v-model="transferDialogOpen"
      :locations="locations"
      :items="items"
      :from-location-id="selectedLocationId"
      @saved="loadStocks"
    />
  </VContainer>
</template>
