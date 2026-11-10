<script setup lang="ts">
import { useDisplay } from 'vuetify'
import {
  type InventoryBrand,
  type InventoryCategory,
  type InventoryItemPayload,
  type InventoryProductPayload,
  createInventoryItem,
  createInventoryProduct,
  updateInventoryItem,
  updateInventoryProduct,
} from '@/api/attendance/inventory'
import InventoryBrandDialog from '@/components/attendance/inventory/InventoryBrandDialog.vue'
import InventoryCategoryDialog from '@/components/attendance/inventory/InventoryCategoryDialog.vue'
import LocationPhotoSlot from '@/components/attendance/locations/LocationPhotoSlot.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { type GoodsEditing, MAX_VARIANT_COMBINATIONS, buildCategoryOptions } from '@/utils/inventoryGoods'

interface OptionRow {
  name: string
  values: string[]
}

type NumberInput = number | string | null

interface VariantRow {
  id: string | null
  isNew: boolean
  attrs: Record<string, string>
  sku_code: string
  codeEdited: boolean
  sale_price: NumberInput
  cost_price: NumberInput
  other_cost: number | null
  barcode: string
  reorder_level: NumberInput
  is_active: boolean
}

const props = defineProps<{
  modelValue: boolean
  editing: GoodsEditing | null
  categories: InventoryCategory[]
  brands: InventoryBrand[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
  lookupsChanged: []
}>()

const display = useDisplay()
const toast = useToast()
const saving = ref(false)
const saveError = ref('')

const form = reactive({
  code: '',
  name_zh: '',
  name_en: '',
  brand_id: null as string | null,
  category_id: null as string | null,
  unit_of_measure: '',
  image_url: '',
  sub_image_url_1: '',
  sub_image_url_2: '',
  sale_price: null as NumberInput,
  cost_price: null as NumberInput,
  other_cost: null as NumberInput,
  barcode: '',
  reorder_level: 0 as NumberInput,
  is_active: true,
})

const imagePreviewError = ref(false)
const subImage1PreviewError = ref(false)
const subImage2PreviewError = ref(false)

const hasVariants = ref(false)
const optionRows = ref<OptionRow[]>([])
const existingRows = ref<VariantRow[]>([])
const newRows = ref<VariantRow[]>([])
const newRowStore = new Map<string, VariantRow>()
const bulk = reactive({ sale_price: null as NumberInput, cost_price: null as NumberInput, reorder_level: null as NumberInput })

const categoryList = ref<InventoryCategory[]>([])
const brandList = ref<InventoryBrand[]>([])
const categoryDialogOpen = ref(false)
const brandDialogOpen = ref(false)

const isEditingItem = computed(() => props.editing?.kind === 'item')
const isEditingProduct = computed(() => props.editing?.kind === 'product')

const categoryOptions = computed(() => buildCategoryOptions(categoryList.value, form.category_id))

const brandOptions = computed(() =>
  brandList.value
    .filter(b => b.is_active || b.id === form.brand_id)
    .map(b => ({ value: b.id, title: [b.name_zh, b.name_en].filter(Boolean).join(' · ') })),
)

function toNumber(value: NumberInput | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function signature(attrs: Record<string, string>): string {
  return JSON.stringify(Object.keys(attrs).sort().map(key => [key, attrs[key]]))
}

const validOptionRows = computed(() => optionRows.value.filter(row => row.name.trim() && row.values.length))
const optionKeys = computed(() => validOptionRows.value.map(row => row.name.trim()))

const combinationCount = computed(() =>
  validOptionRows.value.length ? validOptionRows.value.reduce((total, row) => total * row.values.length, 1) : 0,
)

const tooManyCombinations = computed(() => combinationCount.value > MAX_VARIANT_COMBINATIONS)

const lockedValues = computed(() => {
  const locked = new Map<string, Set<string>>()

  for (const row of existingRows.value) {
    for (const [key, value] of Object.entries(row.attrs)) {
      if (!value)
        continue
      locked.set(key, (locked.get(key) ?? new Set()).add(value))
    }
  }

  return locked
})

function isLocked(name: string, value: string): boolean {
  return !!lockedValues.value.get(name.trim())?.has(value)
}

function rowHasLocked(row: OptionRow): boolean {
  return lockedValues.value.has(row.name.trim())
}

const combos = computed<Record<string, string>[]>(() => {
  if (!validOptionRows.value.length || tooManyCombinations.value)
    return []

  let result: Record<string, string>[] = [{}]

  for (const row of validOptionRows.value) {
    const key = row.name.trim()

    result = result.flatMap(prefix => row.values.map(value => ({ ...prefix, [key]: value })))
  }

  return result
})

function autoCode(attrs: Record<string, string>): string {
  return `${form.code.trim()}-${optionKeys.value.map(key => attrs[key]).join('-')}`
}

function blankRow(attrs: Record<string, string>): VariantRow {
  return reactive({
    id: null,
    isNew: true,
    attrs,
    sku_code: autoCode(attrs),
    codeEdited: false,
    sale_price: null,
    cost_price: null,
    other_cost: null,
    barcode: '',
    reorder_level: 0,
    is_active: true,
  })
}

function refreshNewRows() {
  const taken = new Set(existingRows.value.map(row => signature(row.attrs)))
  const next: VariantRow[] = []

  for (const attrs of combos.value) {
    const key = signature(attrs)

    if (taken.has(key))
      continue

    let row = newRowStore.get(key)

    if (!row) {
      row = blankRow(attrs)
      newRowStore.set(key, row)
    }
    else if (!row.codeEdited) {
      row.sku_code = autoCode(attrs)
    }
    next.push(row)
  }
  newRows.value = next
}

watch([optionRows, () => form.code, existingRows], refreshNewRows, { deep: true })

const allRows = computed(() => [...existingRows.value, ...newRows.value])

function missingKeys(row: VariantRow): string[] {
  return optionKeys.value.filter(key => !row.attrs[key])
}

function optionValuesOf(key: string): string[] {
  return validOptionRows.value.find(row => row.name.trim() === key)?.values ?? []
}

const optionIssue = computed(() => {
  if (!hasVariants.value)
    return ''
  if (!optionRows.value.length)
    return 'Add at least one option (e.g. Size).'

  const names = optionRows.value.map(row => row.name.trim())

  if (optionRows.value.some(row => !row.name.trim() || !row.values.length))
    return 'Every option needs a name and at least one value.'
  if (new Set(names).size !== names.length)
    return 'Option names must be unique.'
  if (tooManyCombinations.value)
    return `Too many combinations (max ${MAX_VARIANT_COMBINATIONS}). Remove some values.`

  return ''
})

const tableIssue = computed(() => {
  if (!hasVariants.value || optionIssue.value)
    return ''
  if (existingRows.value.some(row => missingKeys(row).length))
    return 'Some existing variants still need a value for the new option. Fill them in below.'

  const codes = allRows.value.map(row => row.sku_code.trim())

  if (codes.some(code => !code))
    return 'Every variant needs a code.'
  if (new Set(codes).size !== codes.length)
    return 'Variant codes must be unique.'

  const signatures = allRows.value.map(row => signature(row.attrs))

  if (new Set(signatures).size !== signatures.length)
    return 'Two variants have the same option combination.'

  return ''
})

const canSave = computed(() =>
  !!(form.code.trim() && form.name_zh.trim()) && !optionIssue.value && !tableIssue.value,
)

function toRow(sku: { id: string; sku_code: string; variant_attrs: Record<string, string> | null; sale_price: number | null; cost_price: number | null; other_cost: number | null; barcode: string | null; reorder_level: number; is_active: boolean }): VariantRow {
  return reactive({
    id: sku.id,
    isNew: false,
    attrs: { ...(sku.variant_attrs ?? {}) },
    sku_code: sku.sku_code,
    codeEdited: true,
    sale_price: sku.sale_price,
    cost_price: sku.cost_price,
    other_cost: sku.other_cost,
    barcode: sku.barcode ?? '',
    reorder_level: sku.reorder_level,
    is_active: sku.is_active,
  })
}

function resetForm() {
  const editing = props.editing

  saveError.value = ''
  categoryList.value = [...props.categories]
  brandList.value = [...props.brands]
  newRowStore.clear()
  Object.assign(bulk, { sale_price: null, cost_price: null, reorder_level: null })
  imagePreviewError.value = false
  subImage1PreviewError.value = false
  subImage2PreviewError.value = false
  Object.assign(form, {
    code: '',
    name_zh: '',
    name_en: '',
    brand_id: null,
    category_id: null,
    unit_of_measure: '',
    image_url: '',
    sub_image_url_1: '',
    sub_image_url_2: '',
    sale_price: null,
    cost_price: null,
    other_cost: null,
    barcode: '',
    reorder_level: 0,
    is_active: true,
  })
  hasVariants.value = false
  optionRows.value = []
  existingRows.value = []

  if (editing?.kind === 'item') {
    const item = editing.item

    Object.assign(form, {
      code: item.sku_code,
      name_zh: item.name_zh,
      name_en: item.name_en ?? '',
      brand_id: item.brand_id,
      category_id: item.category_id,
      unit_of_measure: item.unit_of_measure ?? '',
      image_url: item.image_url ?? '',
      sub_image_url_1: item.sub_image_urls[0] ?? '',
      sub_image_url_2: item.sub_image_urls[1] ?? '',
      sale_price: item.sale_price,
      cost_price: item.cost_price,
      other_cost: item.other_cost,
      barcode: item.barcode ?? '',
      reorder_level: item.reorder_level,
      is_active: item.is_active,
    })
  }
  else if (editing?.kind === 'product') {
    const product = editing.product

    Object.assign(form, {
      code: product.code,
      name_zh: product.name_zh,
      name_en: product.name_en ?? '',
      brand_id: product.brand_id,
      category_id: product.category_id,
      unit_of_measure: product.unit_of_measure ?? '',
      image_url: product.image_url ?? '',
      is_active: product.is_active,
    })
    hasVariants.value = true
    optionRows.value = Object.entries(product.options ?? {}).map(([name, values]) => ({ name, values: [...values] }))
    existingRows.value = product.skus
      .filter(sku => sku.variant_attrs && Object.keys(sku.variant_attrs).length)
      .map(toRow)
  }
  refreshNewRows()
}

watch(() => props.modelValue, open => {
  if (open)
    resetForm()
})

function addOptionRow() {
  optionRows.value.push({ name: '', values: [] })
}

function removeOptionRow(index: number) {
  optionRows.value.splice(index, 1)
}

function onValuesUpdate(row: OptionRow, raw: unknown[]) {
  const next: string[] = []

  for (const entry of raw) {
    const value = String(entry).trim()

    if (value && !next.includes(value))
      next.push(value)
  }
  for (const value of lockedValues.value.get(row.name.trim()) ?? []) {
    if (!next.includes(value))
      next.push(value)
  }
  row.values = next
}

function removeValue(row: OptionRow, value: string) {
  if (!isLocked(row.name, value))
    row.values = row.values.filter(v => v !== value)
}

function applyToAll() {
  for (const row of allRows.value) {
    if (toNumber(bulk.sale_price) !== null)
      row.sale_price = toNumber(bulk.sale_price)
    if (toNumber(bulk.cost_price) !== null)
      row.cost_price = toNumber(bulk.cost_price)
    if (toNumber(bulk.reorder_level) !== null)
      row.reorder_level = toNumber(bulk.reorder_level)
  }
}

function onProductActiveChange(active: boolean | null) {
  if (!active)
    return
  for (const row of allRows.value)
    row.is_active = true
}

function onCategorySaved(category: InventoryCategory) {
  categoryList.value = [...categoryList.value.filter(c => c.id !== category.id), category]
  form.category_id = category.id
  emit('lookupsChanged')
}

function onBrandSaved(brand: InventoryBrand) {
  brandList.value = [...brandList.value.filter(b => b.id !== brand.id), brand]
  form.brand_id = brand.id
  emit('lookupsChanged')
}

function buildOptions(): Record<string, string[]> {
  return Object.fromEntries(validOptionRows.value.map(row => [row.name.trim(), [...row.values]]))
}

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''

  const common = {
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    category_id: form.category_id,
    brand_id: form.brand_id,
    unit_of_measure: form.unit_of_measure.trim() || null,
    image_url: form.image_url.trim() || null,
    is_active: form.is_active,
  }

  try {
    if (hasVariants.value) {
      const payload: InventoryProductPayload = {
        ...common,
        code: form.code.trim(),
        options: buildOptions(),
        skus: allRows.value.map(row => ({
          id: row.id,
          sku_code: row.sku_code.trim(),
          variant_attrs: Object.fromEntries(
            optionKeys.value.map(key => [key, row.attrs[key].trim()]),
          ),
          sale_price: toNumber(row.sale_price),
          cost_price: toNumber(row.cost_price),
          other_cost: row.other_cost,
          barcode: row.barcode.trim() || null,
          reorder_level: toNumber(row.reorder_level) ?? 0,
          is_active: form.is_active && row.is_active,
        })),
      }

      if (props.editing?.kind === 'product')
        await updateInventoryProduct(props.editing.product.id, payload)
      else
        await createInventoryProduct(payload)
    }
    else {
      const payload: InventoryItemPayload = {
        ...common,
        sku_code: form.code.trim(),
        barcode: form.barcode.trim() || null,
        cost_price: toNumber(form.cost_price),
        other_cost: toNumber(form.other_cost),
        sale_price: toNumber(form.sale_price),
        reorder_level: toNumber(form.reorder_level) ?? 0,
        sub_image_urls: [form.sub_image_url_1, form.sub_image_url_2].map(s => s.trim()).filter(Boolean),
      }

      if (props.editing?.kind === 'item')
        await updateInventoryItem(props.editing.item.id, payload)
      else
        await createInventoryItem(payload)
    }
    emit('update:modelValue', false)
    emit('saved')
    toast.show(`Item "${common.name_zh}" saved`)
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not save item.')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="960"
    scrollable
    :fullscreen="display.xs.value"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard :title="editing ? 'Edit item' : 'New item'">
      <VCardText>
        <VAlert
          v-if="saveError"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ saveError }}
        </VAlert>

        <div class="text-overline text-medium-emphasis mb-2">
          Basic info
        </div>
        <VRow>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.name_zh"
              label="Name (Chinese)"
              hint="Required. 必填"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.name_en"
              label="Name (English)"
              hint="Optional. 選填"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.code"
              :label="hasVariants ? 'Item code (prefix of variant codes)' : 'Item code'"
              placeholder="TSHIRT"
              hint="Required, must be unique. 必填，不可重複"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.unit_of_measure"
              label="Unit"
              placeholder="pcs / box / set"
              hint="Optional. 選填"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.brand_id"
              :items="brandOptions"
              label="Brand"
              hint="Optional. 選填"
              persistent-hint
              density="comfortable"
              clearable
            >
              <template #append>
                <VBtn
                  icon="ri-add-line"
                  variant="tonal"
                  size="small"
                  aria-label="New brand"
                  @click="brandDialogOpen = true"
                />
              </template>
            </VSelect>
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.category_id"
              :items="categoryOptions"
              label="Category"
              hint="Pick a category or sub-category."
              persistent-hint
              density="comfortable"
              clearable
            >
              <template #append>
                <VBtn
                  icon="ri-add-line"
                  variant="tonal"
                  size="small"
                  aria-label="New category"
                  @click="categoryDialogOpen = true"
                />
              </template>
            </VSelect>
          </VCol>
          <VCol cols="12">
            <VSwitch
              v-model="form.is_active"
              label="Active"
              hint="Inactive items are hidden from pickers; stock history is kept. 停用後唔會出現喺選單，庫存紀錄保留。"
              persistent-hint
              density="comfortable"
              color="primary"
              @update:model-value="onProductActiveChange"
            />
          </VCol>
        </VRow>

        <div class="text-overline text-medium-emphasis mb-2 mt-4">
          Images
        </div>
        <VRow>
          <VCol
            cols="12"
            :md="hasVariants ? 12 : 4"
          >
            <LocationPhotoSlot
              v-model:url="form.image_url"
              v-model:preview-error="imagePreviewError"
              title="Main image"
              hint="Optional. Shown in the list. 選填"
              :preview-max-height="140"
            />
          </VCol>
          <template v-if="!hasVariants">
            <VCol
              cols="12"
              md="4"
            >
              <LocationPhotoSlot
                v-model:url="form.sub_image_url_1"
                v-model:preview-error="subImage1PreviewError"
                title="Sub image 1"
                hint="Optional. 選填"
                :preview-max-height="140"
              />
            </VCol>
            <VCol
              cols="12"
              md="4"
            >
              <LocationPhotoSlot
                v-model:url="form.sub_image_url_2"
                v-model:preview-error="subImage2PreviewError"
                title="Sub image 2"
                hint="Optional. 選填"
                :preview-max-height="140"
              />
            </VCol>
          </template>
        </VRow>

        <div class="text-overline text-medium-emphasis mb-2 mt-4">
          Variants
        </div>
        <VSwitch
          v-model="hasVariants"
          label="This item has variants (e.g. size, colour)"
          :disabled="isEditingItem || isEditingProduct"
          :hint="isEditingItem ? 'Single items cannot be converted to variants yet. 單品暫時唔可以轉做多規格。' : (isEditingProduct ? 'Items with variants cannot be turned back into single items. 多規格貨品不可以改回單品。' : 'Turn on to enter price and barcode for each variant below. 開啟後可喺下面逐個規格填寫。')"
          persistent-hint
          density="comfortable"
          color="primary"
        />

        <template v-if="!hasVariants">
          <VRow class="mt-2">
            <VCol
              cols="12"
              sm="6"
              md="3"
            >
              <VTextField
                v-model.number="form.sale_price"
                label="Sale price"
                type="number"
                min="0"
                step="0.01"
                prefix="HK$"
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="3"
            >
              <VTextField
                v-model.number="form.cost_price"
                label="Cost price"
                type="number"
                min="0"
                step="0.01"
                prefix="HK$"
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="3"
            >
              <VTextField
                v-model.number="form.other_cost"
                label="Other cost"
                type="number"
                min="0"
                step="0.01"
                prefix="HK$"
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="3"
            >
              <VTextField
                v-model.number="form.reorder_level"
                label="Reorder level"
                type="number"
                min="0"
                hint="Stock at or below this is flagged as low. 庫存等於或低於呢個數會標示偏低。"
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VTextField
                v-model="form.barcode"
                label="Barcode"
                prepend-inner-icon="ri-barcode-line"
                hint="Optional. Scan or type. 選填"
                persistent-hint
                density="comfortable"
              />
            </VCol>
          </VRow>
        </template>

        <template v-else>
          <div class="text-body-2 text-medium-emphasis mt-2 mb-3">
            e.g. Size → S, M, L, XL. Type a value, then press Enter or comma. 輸入後按 Enter 或逗號。
          </div>
          <VRow
            v-for="(row, index) in optionRows"
            :key="index"
            align="start"
          >
            <VCol
              cols="12"
              sm="4"
            >
              <VTextField
                v-model="row.name"
                label="Option name"
                placeholder="Size"
                density="comfortable"
                :disabled="rowHasLocked(row)"
                hide-details
              />
            </VCol>
            <VCol
              cols="10"
              sm="7"
            >
              <VCombobox
                :model-value="row.values"
                label="Values"
                multiple
                chips
                :delimiters="[',']"
                density="comfortable"
                hide-details
                @update:model-value="onValuesUpdate(row, $event)"
              >
                <template #chip="{ item }">
                  <VChip
                    size="small"
                    :closable="!isLocked(row.name, String(item.value))"
                    :title="isLocked(row.name, String(item.value)) ? 'Used by existing items; deactivate them in the table below instead. 已有庫存紀錄，可以喺下面停用' : undefined"
                    @click:close="removeValue(row, String(item.value))"
                  >
                    {{ item.title }}
                  </VChip>
                </template>
              </VCombobox>
            </VCol>
            <VCol
              cols="2"
              sm="1"
              class="text-end"
            >
              <VBtn
                icon="ri-delete-bin-line"
                variant="text"
                size="small"
                aria-label="Remove option"
                :disabled="rowHasLocked(row)"
                @click="removeOptionRow(index)"
              />
            </VCol>
          </VRow>
          <VBtn
            variant="tonal"
            color="primary"
            size="small"
            prepend-icon="ri-add-line"
            :disabled="optionRows.length >= 5"
            @click="addOptionRow"
          >
            Add option
          </VBtn>
          <div
            v-if="combinationCount"
            class="text-body-2 mt-3"
            :class="tooManyCombinations ? 'text-error' : 'text-medium-emphasis'"
          >
            {{ combinationCount }} combinations (max {{ MAX_VARIANT_COMBINATIONS }})
          </div>
          <VAlert
            v-if="optionIssue"
            type="warning"
            variant="tonal"
            density="compact"
            class="mt-3"
          >
            {{ optionIssue }}
          </VAlert>

          <template v-if="allRows.length">
            <div class="text-subtitle-2 mt-5 mb-2">
              Variant details
            </div>
            <div class="d-flex flex-wrap align-center gap-3 mb-3">
              <span class="text-body-2 text-medium-emphasis">Apply to all:</span>
              <VTextField
                v-model.number="bulk.sale_price"
                label="Sale price"
                type="number"
                min="0"
                density="compact"
                style="max-width: 130px"
                hide-details
              />
              <VTextField
                v-model.number="bulk.cost_price"
                label="Cost price"
                type="number"
                min="0"
                density="compact"
                style="max-width: 130px"
                hide-details
              />
              <VTextField
                v-model.number="bulk.reorder_level"
                label="Reorder level"
                type="number"
                min="0"
                density="compact"
                style="max-width: 130px"
                hide-details
              />
              <VBtn
                variant="tonal"
                size="small"
                @click="applyToAll"
              >
                Apply
              </VBtn>
            </div>
            <VAlert
              v-if="tableIssue"
              type="warning"
              variant="tonal"
              density="compact"
              class="mb-3"
            >
              {{ tableIssue }}
            </VAlert>
            <div class="overflow-x-auto">
              <VTable density="compact">
                <thead>
                  <tr>
                    <th>Variant</th>
                    <th>Code</th>
                    <th>Sale price</th>
                    <th>Cost price</th>
                    <th>Barcode</th>
                    <th>Reorder level</th>
                    <th>Active</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in allRows"
                    :key="row.id ?? signature(row.attrs)"
                  >
                    <td class="text-no-wrap">
                      <VChip
                        v-for="(value, key) in row.attrs"
                        :key="key"
                        size="x-small"
                        variant="tonal"
                        class="me-1"
                      >
                        {{ key }}: {{ value }}
                      </VChip>
                      <VSelect
                        v-for="key in missingKeys(row)"
                        :key="`missing-${key}`"
                        :model-value="row.attrs[key] ?? null"
                        :items="optionValuesOf(key)"
                        :label="`${key} (required)`"
                        density="compact"
                        class="my-1"
                        style="min-width: 140px"
                        hide-details
                        @update:model-value="row.attrs[key] = $event ?? ''"
                      />
                      <VChip
                        v-if="row.isNew"
                        size="x-small"
                        color="primary"
                        class="ms-1"
                      >
                        New
                      </VChip>
                    </td>
                    <td>
                      <VTextField
                        v-model="row.sku_code"
                        density="compact"
                        style="min-width: 160px"
                        hide-details
                        aria-label="Variant code"
                        @update:model-value="row.codeEdited = true"
                      />
                    </td>
                    <td>
                      <VTextField
                        v-model.number="row.sale_price"
                        type="number"
                        min="0"
                        step="0.01"
                        density="compact"
                        style="min-width: 100px"
                        hide-details
                        aria-label="Sale price"
                      />
                    </td>
                    <td>
                      <VTextField
                        v-model.number="row.cost_price"
                        type="number"
                        min="0"
                        step="0.01"
                        density="compact"
                        style="min-width: 100px"
                        hide-details
                        aria-label="Cost price"
                      />
                    </td>
                    <td>
                      <VTextField
                        v-model="row.barcode"
                        density="compact"
                        style="min-width: 140px"
                        hide-details
                        aria-label="Barcode"
                      />
                    </td>
                    <td>
                      <VTextField
                        v-model.number="row.reorder_level"
                        type="number"
                        min="0"
                        density="compact"
                        style="min-width: 90px"
                        hide-details
                        aria-label="Reorder level"
                      />
                    </td>
                    <td>
                      <VSwitch
                        :model-value="form.is_active && row.is_active"
                        :disabled="!form.is_active"
                        density="compact"
                        color="primary"
                        hide-details
                        aria-label="Active"
                        @update:model-value="row.is_active = !!$event"
                      />
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>
          </template>
        </template>
      </VCardText>
      <VDivider />
      <VCardActions>
        <VSpacer />
        <VBtn
          variant="text"
          @click="emit('update:modelValue', false)"
        >
          Cancel
        </VBtn>
        <VBtn
          color="primary"
          :loading="saving"
          :disabled="!canSave"
          @click="save"
        >
          Save
        </VBtn>
      </VCardActions>
    </VCard>

    <InventoryBrandDialog
      v-model="brandDialogOpen"
      :editing-brand="null"
      @saved="onBrandSaved"
    />
    <InventoryCategoryDialog
      v-model="categoryDialogOpen"
      :editing-category="null"
      :categories="categoryList"
      @saved="onCategorySaved"
    />
  </VDialog>
</template>
