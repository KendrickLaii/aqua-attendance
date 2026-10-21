<script setup lang="ts">
import {
  type InventoryItem,
  createInventoryTransfer,
} from '@/api/attendance/inventory'
import { type LocationItem } from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  locations: LocationItem[]
  items: InventoryItem[]
  fromLocationId: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')

const form = reactive({
  item_id: null as string | null,
  from_location_id: null as string | null,
  to_location_id: null as string | null,
  quantity: null as number | null,
  reason: '',
})

const locationOptions = computed(() =>
  props.locations.map(l => ({
    value: l.id,
    title: [l.name_en, l.name_zh].filter(Boolean).join(' · '),
  })),
)

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
      && form.from_location_id
      && form.to_location_id
      && form.from_location_id !== form.to_location_id
      && form.quantity !== null
      && form.quantity > 0
    ),
)

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  form.item_id = null
  form.from_location_id = props.fromLocationId
  form.to_location_id = null
  form.quantity = null
  form.reason = ''
})

async function save() {
  if (!canSave.value || !form.item_id || !form.from_location_id || !form.to_location_id || form.quantity === null)
    return
  saving.value = true
  saveError.value = ''
  try {
    await createInventoryTransfer({
      item_id: form.item_id,
      from_location_id: form.from_location_id,
      to_location_id: form.to_location_id,
      quantity: form.quantity,
      reason: form.reason.trim() || null,
    })
    emit('update:modelValue', false)
    emit('saved')
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
    max-width="520"
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
          v-model="form.from_location_id"
          :items="locationOptions"
          label="From location"
          density="comfortable"
          class="mb-3"
        />
        <VSelect
          v-model="form.to_location_id"
          :items="locationOptions"
          label="To location"
          hint="Must differ from the source location."
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
