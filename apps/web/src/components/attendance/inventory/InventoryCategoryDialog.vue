<script setup lang="ts">
import {
  type InventoryCategory,
  type InventoryCategoryPayload,
  createInventoryCategory,
  updateInventoryCategory,
} from '@/api/attendance/inventory'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  editingCategory: InventoryCategory | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')

const form = reactive({
  name_zh: '',
  name_en: '',
  is_active: true,
})

const canSave = computed(() => !!form.name_zh.trim())

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  form.name_zh = props.editingCategory?.name_zh ?? ''
  form.name_en = props.editingCategory?.name_en ?? ''
  form.is_active = props.editingCategory?.is_active ?? true
})

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''

  const payload: InventoryCategoryPayload = {
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    is_active: form.is_active,
  }

  try {
    if (props.editingCategory)
      await updateInventoryCategory(props.editingCategory.id, payload)
    else
      await createInventoryCategory(payload)
    emit('update:modelValue', false)
    emit('saved')
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not save category.')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="480"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard :title="editingCategory ? 'Edit category' : 'Add category'">
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
          label="Chinese name"
          hint="Required."
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VTextField
          v-model="form.name_en"
          label="English name"
          hint="Optional."
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VSwitch
          v-model="form.is_active"
          label="Active category"
          density="comfortable"
          color="primary"
          hide-details
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
