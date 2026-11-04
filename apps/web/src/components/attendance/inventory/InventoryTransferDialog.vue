<script setup lang="ts">
import { useDisplay } from 'vuetify'
import {
  type InventoryItem,
  type InventoryWarehouse,
  createInventoryTransfer,
} from '@/api/attendance/inventory'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  warehouses: InventoryWarehouse[]
  items: InventoryItem[]
  fromWarehouseId: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const display = useDisplay()
const toast = useToast()
const saving = ref(false)
const saveError = ref('')

const form = reactive({
  item_id: null as string | null,
  from_warehouse_id: null as string | null,
  to_warehouse_id: null as string | null,
  quantity: null as number | null,
  reason: '',
})

const warehouseOptions = computed(() =>
  props.warehouses.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

const itemLabel = computed(() => props.items.find(i => i.id === form.item_id)?.sku_code ?? '')

const itemOptions = computed(() =>
  props.items
    .filter(i => i.is_active)
    .map(i => ({
      value: i.id,
      title: [i.sku_code, i.name_zh, i.name_en].filter(Boolean).join(' · '),
    })),
)

const canSave = computed(
  () =>
    !!(
      form.item_id
      && form.from_warehouse_id
      && form.to_warehouse_id
      && form.from_warehouse_id !== form.to_warehouse_id
      && form.quantity !== null
      && form.quantity > 0
    ),
)

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  form.item_id = null
  form.from_warehouse_id = props.fromWarehouseId
  form.to_warehouse_id = null
  form.quantity = null
  form.reason = ''
})

async function save() {
  if (!canSave.value || !form.item_id || !form.from_warehouse_id || !form.to_warehouse_id || form.quantity === null)
    return
  saving.value = true
  saveError.value = ''
  try {
    await createInventoryTransfer({
      item_id: form.item_id,
      from_warehouse_id: form.from_warehouse_id,
      to_warehouse_id: form.to_warehouse_id,
      quantity: form.quantity,
      reason: form.reason.trim() || null,
    })
    emit('update:modelValue', false)
    emit('saved')
    toast.show(`Transferred ${form.quantity} × ${itemLabel.value}`)
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not create transfer.')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="560"
    :fullscreen="display.xs.value"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard title="Transfer stock 調撥">
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
        <VAutocomplete
          v-model="form.item_id"
          :items="itemOptions"
          label="Item"
          hint="Required."
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VSelect
          v-model="form.from_warehouse_id"
          :items="warehouseOptions"
          label="From warehouse 倉庫"
          density="comfortable"
          class="mb-3"
        />
        <VSelect
          v-model="form.to_warehouse_id"
          :items="warehouseOptions"
          label="To warehouse 倉庫"
          hint="Must differ from the source warehouse."
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VTextField
          v-model.number="form.quantity"
          label="Quantity"
          type="number"
          min="1"
          hint="Units to move. Cannot exceed the source's available stock."
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VTextField
          v-model="form.reason"
          label="Reason"
          hint="Optional."
          persistent-hint
          density="comfortable"
        />
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
          Transfer
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>
