<script setup lang="ts">
import {
  type InventoryItem,
  type InventoryMovementType,
  createInventoryMovement,
} from '@/api/attendance/inventory'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  locationId: string | null
  items: InventoryItem[]
  initialType?: InventoryMovementType
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')

const form = reactive({
  item_id: null as string | null,
  type: 'in' as InventoryMovementType,
  quantity: null as number | null,
  reason_code: null as string | null,
  reason: '',
  reference: '',
})

const typeOptions = [
  { value: 'in' as const, title: 'Stock in (入庫)' },
  { value: 'out' as const, title: 'Stock out (出庫)' },
  { value: 'adjust' as const, title: 'Adjust to count (調整)' },
]

const inReasonOptions = [
  { value: 'opening', title: 'Opening stock 期初庫存' },
  { value: 'sales_return', title: 'Sales return 銷售退回' },
  { value: 'other', title: 'Other 其他' },
]

const outReasonOptions = [
  { value: 'damage', title: 'Damage 損毀報廢' },
  { value: 'loss', title: 'Loss 遺失' },
  { value: 'gift', title: 'Gift 贈送' },
  { value: 'sample', title: 'Sample 樣品' },
  { value: 'internal_use', title: 'Internal use 內部使用' },
  { value: 'supplier_return', title: 'Supplier return 退貨' },
  { value: 'sale', title: 'Sale 銷售' },
  { value: 'other', title: 'Other 其他' },
]

const REASON_CODES_REQUIRING_NOTE = new Set(['damage', 'loss', 'gift'])

const reasonCodeOptions = computed(() => {
  if (form.type === 'in')
    return inReasonOptions
  if (form.type === 'out')
    return outReasonOptions

  return []
})

const noteRequired = computed(
  () => !!form.reason_code && REASON_CODES_REQUIRING_NOTE.has(form.reason_code),
)

const itemOptions = computed(() =>
  props.items
    .filter(i => i.is_active)
    .map(i => ({
      value: i.id,
      title: [i.sku_code, i.name_zh, i.name_en].filter(Boolean).join(' · '),
    })),
)

const quantityLabel = computed(() =>
  form.type === 'adjust' ? 'New on-hand count' : 'Quantity',
)

const quantityHint = computed(() =>
  form.type === 'adjust'
    ? 'The absolute count after adjustment; the delta is computed automatically.'
    : 'Units to add or remove. Stock out cannot exceed the on-hand balance.',
)

const canSave = computed(
  () =>
    !!(
      props.locationId
      && form.item_id
      && form.quantity !== null
      && form.quantity >= 0
      && (form.type === 'adjust' || form.quantity > 0)
      && (!noteRequired.value || !!form.reason.trim())
    ),
)

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  form.item_id = null
  form.type = props.initialType ?? 'in'
  form.quantity = null
  form.reason_code = null
  form.reason = ''
  form.reference = ''
})

watch(() => form.type, () => {
  form.reason_code = null
})

async function save() {
  if (!canSave.value || !props.locationId || !form.item_id || form.quantity === null)
    return
  saving.value = true
  saveError.value = ''
  try {
    await createInventoryMovement({
      item_id: form.item_id,
      location_id: props.locationId,
      type: form.type,
      quantity: form.quantity,
      reason: form.reason.trim() || null,
      reason_code: form.reason_code,
      reference: form.reference.trim() || null,
    })
    emit('update:modelValue', false)
    emit('saved')
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not record movement.')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="520"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard title="Record stock movement">
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
        <VSelect
          v-model="form.type"
          :items="typeOptions"
          label="Movement type"
          density="comfortable"
          class="mb-3"
        />
        <VAutocomplete
          v-model="form.item_id"
          :items="itemOptions"
          label="Item"
          hint="Required."
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VTextField
          v-model.number="form.quantity"
          :label="quantityLabel"
          :hint="quantityHint"
          persistent-hint
          type="number"
          min="0"
          density="comfortable"
          class="mb-3"
        />
        <VSelect
          v-if="reasonCodeOptions.length"
          v-model="form.reason_code"
          :items="reasonCodeOptions"
          label="Reason code"
          :hint="noteRequired ? 'A note is required for this reason.' : 'Optional.'"
          persistent-hint
          density="comfortable"
          class="mb-3"
          clearable
        />
        <VTextField
          v-model="form.reason"
          label="Reason"
          :hint="noteRequired ? 'Required for damage / loss / gift.' : 'Optional, e.g. 入貨 / 客戶購買 / 盤點差異.'"
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VTextField
          v-model="form.reference"
          label="Reference"
          hint="Optional. Repeating the same reference is ignored (idempotent)."
          persistent-hint
          density="comfortable"
        />
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
