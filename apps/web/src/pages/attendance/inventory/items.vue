<script setup lang="ts">
import {
  type InventoryBrand,
  type InventoryCategory,
  type InventoryItem,
  type InventoryProduct,
  exportInventoryItemsCSV,
  importInventoryItemsCSV,
  listInventoryBrands,
  listInventoryCategories,
  listInventoryItems,
  listInventoryProducts,
} from '@/api/attendance/inventory'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import InventoryGoodsDialog from '@/components/attendance/inventory/InventoryGoodsDialog.vue'
import InventoryItemImage from '@/components/attendance/inventory/InventoryItemImage.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatMoney } from '@/utils/inventoryDisplay'
import {
  type GoodsEditing,
  buildCategoryOptions,
  buildOptionSuggestions,
  categoryIdsWithChildren,
  categoryPath,
} from '@/utils/inventoryGoods'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

interface GoodsRow {
  key: string
  product: InventoryProduct | null
  item: InventoryItem | null
  name: string
  code: string
  imageUrl: string | null
  brandId: string | null
  categoryId: string | null
  isActive: boolean
  variants: InventoryItem[]
  variantCount: number
  prices: number[]
  onHand: number
  lowStock: boolean
}

const { ensureAccess } = useAttendanceAdminGate()
const toast = useToast()

const loading = ref(true)
const loadError = ref('')

useAutoClearAlerts(loadError)

const categories = ref<InventoryCategory[]>([])
const brands = ref<InventoryBrand[]>([])
const items = ref<InventoryItem[]>([])
const products = ref<InventoryProduct[]>([])

const search = ref('')
const brandFilter = ref<string | null>(null)
const categoryFilter = ref<string | null>(null)
const showInactive = ref(false)
const expanded = ref<Set<string>>(new Set())

const goodsDialogOpen = ref(false)
const editing = ref<GoodsEditing | null>(null)
const importInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)

const optionSuggestions = computed(() => buildOptionSuggestions(products.value))
const brandById = computed(() => new Map(brands.value.map(b => [b.id, b])))
const categoryOptions = computed(() => buildCategoryOptions(categories.value))

const brandOptions = computed(() =>
  brands.value
    .filter(b => b.is_active)
    .map(b => ({ value: b.id, title: [b.name_zh, b.name_en].filter(Boolean).join(' · ') })),
)

function isLow(item: InventoryItem): boolean {
  return item.is_active && item.reorder_level > 0 && item.on_hand <= item.reorder_level
}

const goodsRows = computed<GoodsRow[]>(() => {
  const term = search.value.trim().toLowerCase()

  const matches = (values: (string | null | undefined)[]) =>
    !term || values.some(v => (v ?? '').toLowerCase().includes(term))

  const categoryIds = categoryFilter.value ? categoryIdsWithChildren(categories.value, categoryFilter.value) : null
  const categoryOk = (id: string | null) => !categoryIds || (!!id && categoryIds.has(id))
  const brandOk = (id: string | null) => !brandFilter.value || id === brandFilter.value
  const skusByProduct = new Map<string, InventoryItem[]>()

  for (const item of items.value) {
    if (item.product_id)
      skusByProduct.set(item.product_id, [...(skusByProduct.get(item.product_id) ?? []), item])
  }

  const rows: GoodsRow[] = []

  for (const product of products.value) {
    if ((!showInactive.value && !product.is_active) || !brandOk(product.brand_id) || !categoryOk(product.category_id))
      continue

    const allSkus = skusByProduct.get(product.id) ?? []
    const productMatches = matches([product.code, product.name_zh, product.name_en])

    const variants = allSkus
      .filter(sku => showInactive.value || sku.is_active)
      .filter(sku => productMatches || matches([sku.sku_code, sku.name_zh, sku.name_en, sku.barcode]))
      .sort((a, b) => a.sku_code.localeCompare(b.sku_code, undefined, { numeric: true }))

    if (term && !productMatches && !variants.length)
      continue

    rows.push({
      key: `p-${product.id}`,
      product,
      item: null,
      name: product.name_zh,
      code: product.code,
      imageUrl: product.image_url,
      brandId: product.brand_id,
      categoryId: product.category_id,
      isActive: product.is_active,
      variants,
      variantCount: allSkus.length,
      prices: allSkus.filter(sku => sku.is_active && sku.sale_price !== null).map(sku => sku.sale_price as number),
      onHand: allSkus.reduce((total, sku) => total + sku.on_hand, 0),
      lowStock: allSkus.some(isLow),
    })
  }

  for (const item of items.value) {
    if (item.product_id)
      continue
    if (!showInactive.value && !item.is_active)
      continue
    if (!brandOk(item.brand_id) || !categoryOk(item.category_id))
      continue
    if (!matches([item.sku_code, item.name_zh, item.name_en, item.barcode]))
      continue
    rows.push({
      key: `i-${item.id}`,
      product: null,
      item,
      name: item.name_zh,
      code: item.sku_code,
      imageUrl: item.image_url,
      brandId: item.brand_id,
      categoryId: item.category_id,
      isActive: item.is_active,
      variants: [],
      variantCount: 0,
      prices: item.sale_price === null ? [] : [item.sale_price],
      onHand: item.on_hand,
      lowStock: isLow(item),
    })
  }

  return rows.sort((a, b) =>
    a.name.localeCompare(b.name, 'zh-Hant', { numeric: true }) || a.code.localeCompare(b.code, undefined, { numeric: true }),
  )
})

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  await loadAll()

  if (route.query.action === 'new') {
    openCreate()

    const rest = { ...route.query }

    delete rest.action
    router.replace({ query: rest })
  }
})

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [categoryList, brandList, itemList, productList] = await Promise.all([
      listInventoryCategories(),
      listInventoryBrands(),
      listInventoryItems(),
      listInventoryProducts(),
    ])

    categories.value = categoryList
    brands.value = brandList
    items.value = itemList
    products.value = productList
  }
  catch (e) {
    console.error('Failed to load inventory items', e)
    loadError.value = formatApiError(e, 'Failed to load items.')
  }
  finally {
    loading.value = false
  }
}

async function reloadLookups() {
  try {
    const [categoryList, brandList] = await Promise.all([listInventoryCategories(), listInventoryBrands()])

    categories.value = categoryList
    brands.value = brandList
  }
  catch (e) {
    console.error('Failed to reload categories and brands', e)
  }
}

function openCreate() {
  editing.value = null
  goodsDialogOpen.value = true
}

function openEdit(row: GoodsRow) {
  if (row.product)
    editing.value = { kind: 'product', product: row.product }
  else if (row.item)
    editing.value = { kind: 'item', item: row.item }
  goodsDialogOpen.value = true
}

function toggleExpanded(key: string) {
  const next = new Set(expanded.value)

  if (!next.delete(key))
    next.add(key)
  expanded.value = next
}

function priceLabel(prices: number[]): string {
  if (!prices.length)
    return '—'

  const min = Math.min(...prices)
  const max = Math.max(...prices)

  return min === max ? formatMoney(min) : `${formatMoney(min)} – ${formatMoney(max)}`
}

function brandLabel(brandId: string | null): string {
  const brand = brandId ? brandById.value.get(brandId) : undefined

  return brand ? brand.name_zh : '—'
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
    toast.show(formatApiError(e, 'Export failed.'), 'error', 6000)
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
  try {
    const result = await importInventoryItemsCSV(file)

    toast.show(`Imported: ${result.created} created, ${result.updated} updated${result.skipped ? `, ${result.skipped} skipped` : ''}`)
    await loadAll()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Import failed.'), 'error', 6000)
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
          Inventory Items
        </div>
        <div class="text-body-2 text-medium-emphasis">
          Manage items, prices and variants. 管理貨品、價錢同規格。
        </div>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex flex-wrap gap-2"
      >
        <VMenu>
          <template #activator="{ props: menuProps }">
            <VBtn
              v-bind="menuProps"
              variant="tonal"
              color="primary"
              prepend-icon="ri-more-2-line"
              :loading="importing"
            >
              CSV
            </VBtn>
          </template>
          <VList density="compact">
            <VListItem
              prepend-icon="ri-download-line"
              title="Export CSV"
              @click="exportItems"
            />
            <VListItem
              prepend-icon="ri-upload-line"
              title="Import CSV"
              @click="pickImportFile"
            />
          </VList>
        </VMenu>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-price-tag-3-line"
          :to="{ name: 'attendance-inventory-categories' }"
        >
          Categories & Brands
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          New item
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

    <VCard v-else>
      <VCardText class="d-flex flex-wrap gap-3 align-center">
        <VTextField
          v-model="search"
          label="Search (name / code / barcode)"
          prepend-inner-icon="ri-search-line"
          density="comfortable"
          style="max-width: 300px"
          hide-details
          clearable
        />
        <VSelect
          v-model="brandFilter"
          :items="brandOptions"
          label="Brand"
          density="comfortable"
          style="max-width: 200px"
          hide-details
          clearable
        />
        <VSelect
          v-model="categoryFilter"
          :items="categoryOptions"
          label="Category"
          density="comfortable"
          style="max-width: 260px"
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
              <th style="width: 48px" />
              <th style="width: 64px" />
              <th>Item</th>
              <th>Brand</th>
              <th>Category</th>
              <th class="text-end">
                Sale price
              </th>
              <th class="text-end">
                Stock
              </th>
              <th>Status</th>
              <th class="text-end">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="row in goodsRows"
              :key="row.key"
            >
              <tr :class="{ 'text-disabled': !row.isActive }">
                <td>
                  <VBtn
                    v-if="row.product"
                    :icon="expanded.has(row.key) ? 'ri-arrow-down-s-line' : 'ri-arrow-right-s-line'"
                    variant="text"
                    size="small"
                    :aria-label="expanded.has(row.key) ? 'Collapse variants' : 'Expand variants'"
                    @click="toggleExpanded(row.key)"
                  />
                </td>
                <td>
                  <InventoryItemImage :url="row.imageUrl" />
                </td>
                <td>
                  <div class="font-weight-medium">
                    {{ row.name }}
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    {{ row.code }}<template v-if="row.product">
                      · {{ row.variantCount }} variants
                    </template>
                  </div>
                </td>
                <td>{{ brandLabel(row.brandId) }}</td>
                <td>{{ categoryPath(categories, row.categoryId) }}</td>
                <td class="text-end tabular-nums">
                  {{ priceLabel(row.prices) }}
                </td>
                <td class="text-end tabular-nums">
                  <VChip
                    v-if="row.lowStock"
                    color="warning"
                    size="small"
                    variant="tonal"
                    title="A variant is low on stock"
                  >
                    {{ row.onHand }}
                  </VChip>
                  <template v-else>
                    {{ row.onHand }}
                  </template>
                </td>
                <td>
                  <VChip
                    :color="row.isActive ? 'success' : 'default'"
                    size="small"
                    variant="tonal"
                  >
                    {{ row.isActive ? 'Active' : 'Inactive' }}
                  </VChip>
                </td>
                <td class="text-end">
                  <VBtn
                    icon="ri-pencil-line"
                    variant="text"
                    size="small"
                    aria-label="Edit item"
                    @click="openEdit(row)"
                  />
                </td>
              </tr>
              <tr
                v-if="row.product && expanded.has(row.key)"
                class="bg-surface-variant"
              >
                <td colspan="2" />
                <td colspan="7">
                  <VTable
                    v-if="row.variants.length"
                    density="compact"
                    class="bg-transparent"
                  >
                    <thead>
                      <tr>
                        <th>Variant</th>
                        <th>Code</th>
                        <th class="text-end">
                          Sale price
                        </th>
                        <th class="text-end">
                          Cost price
                        </th>
                        <th>Barcode</th>
                        <th class="text-end">
                          Stock
                        </th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="variant in row.variants"
                        :key="variant.id"
                        :class="{ 'text-disabled': !variant.is_active }"
                      >
                        <td>
                          <VChip
                            v-for="(value, key) in variant.variant_attrs ?? {}"
                            :key="key"
                            size="x-small"
                            variant="tonal"
                            class="me-1"
                          >
                            {{ key }}: {{ value }}
                          </VChip>
                          <span v-if="!variant.variant_attrs">—</span>
                        </td>
                        <td>{{ variant.sku_code }}</td>
                        <td class="text-end tabular-nums">
                          {{ formatMoney(variant.sale_price) }}
                        </td>
                        <td class="text-end tabular-nums">
                          {{ formatMoney(variant.cost_price) }}
                        </td>
                        <td>{{ variant.barcode || '—' }}</td>
                        <td class="text-end tabular-nums">
                          <VChip
                            v-if="variant.is_active && variant.reorder_level > 0 && variant.on_hand <= variant.reorder_level"
                            color="warning"
                            size="x-small"
                            variant="tonal"
                          >
                            {{ variant.on_hand }}
                          </VChip>
                          <template v-else>
                            {{ variant.on_hand }}
                          </template>
                        </td>
                        <td>
                          <VChip
                            :color="variant.is_active ? 'success' : 'default'"
                            size="x-small"
                            variant="tonal"
                          >
                            {{ variant.is_active ? 'Active' : 'Inactive' }}
                          </VChip>
                        </td>
                      </tr>
                    </tbody>
                  </VTable>
                  <div
                    v-else
                    class="text-body-2 text-medium-emphasis py-2"
                  >
                    No variants match the filters.
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="goodsRows.length === 0">
              <td colspan="9">
                <InventoryEmptyState
                  icon="ri-archive-line"
                  :text="items.length || products.length ? 'No items match the filters.' : 'No items yet'"
                  :action-label="items.length || products.length ? undefined : 'New item'"
                  @action="openCreate"
                />
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
    </VCard>

    <InventoryGoodsDialog
      v-model="goodsDialogOpen"
      :editing="editing"
      :categories="categories"
      :brands="brands"
      :option-suggestions="optionSuggestions"
      @saved="loadAll"
      @lookups-changed="reloadLookups"
    />
  </VContainer>
</template>
