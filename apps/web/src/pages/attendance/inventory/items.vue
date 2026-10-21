<script setup lang="ts">
import {
  type InventoryCategory,
  type InventoryItem,
  exportInventoryItemsCSV,
  importInventoryItemsCSV,
  listInventoryCategories,
  listInventoryItems,
} from '@/api/attendance/inventory'
import InventoryCategoryDialog from '@/components/attendance/inventory/InventoryCategoryDialog.vue'
import InventoryItemDialog from '@/components/attendance/inventory/InventoryItemDialog.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const categories = ref<InventoryCategory[]>([])
const items = ref<InventoryItem[]>([])

const search = ref('')
const categoryFilter = ref<string | null>(null)
const showInactive = ref(false)

const itemDialogOpen = ref(false)
const editingItem = ref<InventoryItem | null>(null)
const categoryDialogOpen = ref(false)
const editingCategory = ref<InventoryCategory | null>(null)
const importInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const importResult = ref('')

const categoryById = computed(() => new Map(categories.value.map(c => [c.id, c])))

const categoryOptions = computed(() =>
  categories.value
    .filter(c => c.is_active)
    .map(c => ({ value: c.id, title: [c.name_zh, c.name_en].filter(Boolean).join(' · ') })),
)

const filteredItems = computed(() => {
  const term = search.value.trim().toLowerCase()

  return items.value.filter(item => {
    if (!showInactive.value && !item.is_active)
      return false
    if (categoryFilter.value && item.category_id !== categoryFilter.value)
      return false

    return !(
      term
      && ![item.sku_code, item.name_zh, item.name_en ?? '']
        .some(v => v.toLowerCase().includes(term))
    )
  })
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
    const [categoryList, itemList] = await Promise.all([
      listInventoryCategories(),
      listInventoryItems(),
    ])

    categories.value = categoryList
    items.value = [...itemList].sort((a, b) =>
      a.sku_code.localeCompare(b.sku_code, undefined, { numeric: true }),
    )
  }
  catch (e) {
    console.error('Failed to load inventory items', e)
    loadError.value = formatApiError(e, 'Failed to load inventory items.')
  }
  finally {
    loading.value = false
  }
}

function openCreateItem() {
  editingItem.value = null
  itemDialogOpen.value = true
}

function openEditItem(item: InventoryItem) {
  editingItem.value = item
  itemDialogOpen.value = true
}

function openCreateCategory() {
  editingCategory.value = null
  categoryDialogOpen.value = true
}

function openEditCategory(category: InventoryCategory) {
  editingCategory.value = category
  categoryDialogOpen.value = true
}

async function exportItems() {
  try {
    const blob = await exportInventoryItemsCSV()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = 'inventory_items.csv'
    link.click()
    URL.revokeObjectURL(url)
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Export failed.')
  }
}

function pickImportFile() {
  importInput.value?.click()
}

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  input.value = ''
  if (!file)
    return
  importing.value = true
  importResult.value = ''
  try {
    const result = await importInventoryItemsCSV(file)

    importResult.value = `Imported: ${result.created} created, ${result.updated} updated.`
    await loadAll()
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Items import failed.')
  }
  finally {
    importing.value = false
  }
}

function categoryLabel(categoryId: string | null): string {
  if (!categoryId)
    return '—'
  const category = categoryById.value.get(categoryId)

  return category ? [category.name_zh, category.name_en].filter(Boolean).join(' · ') : '—'
}

function money(value: number | null): string {
  return value === null ? '—' : `HK$${value.toFixed(2)}`
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
          Inventory Items 品項
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-download-line"
          @click="exportItems"
        >
          Export CSV
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-upload-line"
          :loading="importing"
          @click="pickImportFile"
        >
          Import CSV
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreateCategory"
        >
          Add Category
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreateItem"
        >
          Add Item
        </VBtn>
        <input
          ref="importInput"
          type="file"
          accept=".csv,text/csv"
          class="d-none"
          @change="onImportFile"
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

    <VAlert
      v-if="importResult"
      type="success"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="importResult = ''"
    >
      {{ importResult }}
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
      <VCard class="mb-4">
        <VCardTitle class="text-subtitle-1">
          Categories
        </VCardTitle>
        <VCardText>
          <VChip
            v-for="category in categories"
            :key="category.id"
            class="me-2 mb-2"
            :variant="category.is_active ? 'tonal' : 'outlined'"
            :color="category.is_active ? 'primary' : 'default'"
            @click="openEditCategory(category)"
          >
            {{ [category.name_zh, category.name_en].filter(Boolean).join(' · ') }}
            <template v-if="!category.is_active">
              (inactive)
            </template>
          </VChip>
          <div
            v-if="categories.length === 0"
            class="text-medium-emphasis"
          >
            No categories yet — click "Add Category" first.
          </div>
        </VCardText>
      </VCard>

      <VCard>
        <VCardText class="d-flex flex-wrap gap-3 align-center">
          <VTextField
            v-model="search"
            label="Search item"
            prepend-inner-icon="ri-search-line"
            density="comfortable"
            style="max-width: 280px"
            hide-details
            clearable
          />
          <VSelect
            v-model="categoryFilter"
            :items="categoryOptions"
            label="Category"
            density="comfortable"
            style="max-width: 240px"
            hide-details
            clearable
          />
          <VSwitch
            v-model="showInactive"
            label="Show inactive"
            density="comfortable"
            color="primary"
            hide-details
          />
        </VCardText>
        <div class="overflow-x-auto">
          <VTable>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th>Category</th>
                <th>Unit</th>
                <th class="text-end">
                  Cost
                </th>
                <th class="text-end">
                  Sale
                </th>
                <th class="text-end">
                  Reorder level
                </th>
                <th>Status</th>
                <th class="text-end">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in filteredItems"
                :key="item.id"
              >
                <td>{{ item.sku_code }}</td>
                <td>{{ [item.name_zh, item.name_en].filter(Boolean).join(' · ') }}</td>
                <td>{{ categoryLabel(item.category_id) }}</td>
                <td>{{ item.unit_of_measure || '—' }}</td>
                <td class="text-end tabular-nums">
                  {{ money(item.cost_price) }}
                </td>
                <td class="text-end tabular-nums">
                  {{ money(item.sale_price) }}
                </td>
                <td class="text-end tabular-nums">
                  {{ item.reorder_level }}
                </td>
                <td>
                  <VChip
                    :color="item.is_active ? 'success' : 'default'"
                    size="small"
                    variant="tonal"
                  >
                    {{ item.is_active ? 'Active' : 'Inactive' }}
                  </VChip>
                </td>
                <td class="text-end">
                  <VBtn
                    icon="ri-pencil-line"
                    variant="text"
                    size="small"
                    aria-label="Edit item"
                    @click="openEditItem(item)"
                  />
                </td>
              </tr>
              <tr v-if="filteredItems.length === 0">
                <td
                  colspan="9"
                  class="text-center text-medium-emphasis py-8"
                >
                  No items match. Use “Add Item” to create one.
                </td>
              </tr>
            </tbody>
          </VTable>
        </div>
      </VCard>
    </template>

    <InventoryItemDialog
      v-model="itemDialogOpen"
      :editing-item="editingItem"
      :category-options="categoryOptions"
      @saved="loadAll"
    />
    <InventoryCategoryDialog
      v-model="categoryDialogOpen"
      :editing-category="editingCategory"
      @saved="loadAll"
    />
  </VContainer>
</template>
