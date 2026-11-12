<script setup lang="ts">
import { useDisplay } from 'vuetify'
import {
  type InventoryBrand,
  type InventoryBrandPayload,
  createInventoryBrand,
  updateInventoryBrand,
} from '@/api/attendance/inventory'
import { formatApiError } from '@/utils/formatApiDetail'
import { NAME_REQUIRED_HINT, namesMissing, zhForEdit } from '@/utils/inventoryGoods'

const props = defineProps<{
  modelValue: boolean
  editingBrand: InventoryBrand | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [brand: InventoryBrand]
}>()

const display = useDisplay()
const toast = useToast()
const saving = ref(false)
const saveError = ref('')

const form = reactive({
  name_zh: '',
  name_en: '',
  is_active: true,
})

const namesTouched = ref(false)

const namesHint = computed(() =>
  namesTouched.value && namesMissing(form.name_zh, form.name_en) ? NAME_REQUIRED_HINT : undefined,
)

const canSave = computed(() => !namesMissing(form.name_zh, form.name_en))

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  namesTouched.value = false
  form.name_zh = zhForEdit(props.editingBrand?.name_zh, props.editingBrand?.name_en)
  form.name_en = props.editingBrand?.name_en ?? ''
  form.is_active = props.editingBrand?.is_active ?? true
})

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''

  const payload: InventoryBrandPayload = {
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    is_active: form.is_active,
  }

  try {
    const saved = props.editingBrand
      ? await updateInventoryBrand(props.editingBrand.id, payload)
      : await createInventoryBrand(payload)

    emit('update:modelValue', false)
    emit('saved', saved)
    toast.show(`Brand "${payload.name_zh || payload.name_en}" saved`)
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not save brand.')
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
    <VCard :title="editingBrand ? 'Edit brand' : 'New brand'">
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
        <VTextField
          v-model="form.name_zh"
          label="Name (Chinese)"
          :hint="namesHint"
          :persistent-hint="!!namesHint"
          density="comfortable"
          class="mb-3"
          @update:model-value="namesTouched = true"
        />
        <VTextField
          v-model="form.name_en"
          label="Name (English)"
          density="comfortable"
          class="mb-3"
          @update:model-value="namesTouched = true"
        />
        <VSwitch
          v-model="form.is_active"
          label="Active"
          density="comfortable"
          color="primary"
          hide-details
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
          Save
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>
