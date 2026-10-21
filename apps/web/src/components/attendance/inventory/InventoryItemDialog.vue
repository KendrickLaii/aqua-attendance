<script setup lang="ts">
import {
  type InventoryItem,
  type InventoryItemPayload,
  createInventoryItem,
  updateInventoryItem,
} from '@/api/attendance/inventory'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  editingItem: InventoryItem | null
  categoryOptions: { value: string; title: string }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')

const form = reactive({
  sku_code: '',
  name_zh: '',
  name_en: '',
  category_id: null as string | null,
  unit_of_measure: '',
  cost_price: null as number | null,
  sale_price: null as number | null,
  reorder_level: 0,
  is_active: true,
})

const canSave = computed(() => !!(form.sku_code.trim() && form.name_zh.trim()))

function resetForm(item: InventoryItem | null) {
  if (item) {
    Object.assign(form, {
      sku_code: item.sku_code,
      name_zh: item.name_zh,
      name_en: item.name_en ?? '',
      category_id: item.category_id,
      unit_of_measure: item.unit_of_measure ?? '',
      cost_price: item.cost_price,
      sale_price: item.sale_price,
      reorder_level: item.reorder_level,
      is_active: item.is_active,
    })

    return
  }
  Object.assign(form, {
    sku_code: '',
    name_zh: '',
    name_en: '',
    category_id: null,
    unit_of_measure: '',
    cost_price: null,
    sale_price: null,
    reorder_level: 0,
    is_active: true,
  })
}

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  resetForm(props.editingItem)
})

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''

  const payload: InventoryItemPayload = {
    sku_code: form.sku_code.trim(),
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    category_id: form.category_id,
    unit_of_measure: form.unit_of_measure.trim() || null,
    cost_price: form.cost_price,
    sale_price: form.sale_price,
    reorder_level: form.reorder_level ?? 0,
    is_active: form.is_active,
  }

  try {
    if (props.editingItem)
      await updateInventoryItem(props.editingItem.id, payload)
    else
      await createInventoryItem(payload)
    emit('update:modelValue', false)
    emit('saved')
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
    max-width="640"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard :title="editingItem ? 'Edit item' : 'Add item'">
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

        <VRow>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="form.sku_code"
              label="SKU code"
              placeholder="BK-MATH-P3"
              hint="Unique. Required."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.category_id"
              :items="categoryOptions"
              label="Category"
              hint="Optional."
              persistent-hint
              density="comfortable"
              clearable
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_zh"
              label="Chinese name"
              hint="Required."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_en"
              label="English name"
              hint="Optional."
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
              label="Unit of measure"
              placeholder="pcs / box / set"
              hint="Optional."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model.number="form.reorder_level"
              label="Reorder level"
              type="number"
              min="0"
              hint="Stock at or below this is flagged as low."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model.number="form.cost_price"
              label="Cost price"
              type="number"
              min="0"
              step="0.01"
              prefix="HK$"
              hint="Optional."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model.number="form.sale_price"
              label="Sale price"
              type="number"
              min="0"
              step="0.01"
              prefix="HK$"
              hint="Optional."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VSwitch
              v-model="form.is_active"
              label="Active item"
              hint="Off: hidden from pickers. Stock history stays."
              persistent-hint
              density="comfortable"
              color="primary"
            />
          </VCol>
        </VRow>
      </VCardText>
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
  </VDialog>
</template>
