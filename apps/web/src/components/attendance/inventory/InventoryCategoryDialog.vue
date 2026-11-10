<script setup lang="ts">
import { useDisplay } from 'vuetify'
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
  categories: InventoryCategory[]
  defaultParentId?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [category: InventoryCategory]
}>()

const display = useDisplay()
const toast = useToast()
const saving = ref(false)
const saveError = ref('')

const form = reactive({
  name_zh: '',
  name_en: '',
  parent_id: null as string | null,
  is_active: true,
})

const canSave = computed(() => !!form.name_zh.trim())

const hasChildren = computed(() =>
  !!props.editingCategory && props.categories.some(c => c.parent_id === props.editingCategory?.id),
)

const parentOptions = computed(() =>
  props.categories
    .filter(c => !c.parent_id && c.is_active && c.id !== props.editingCategory?.id)
    .map(c => ({ value: c.id, title: [c.name_zh, c.name_en].filter(Boolean).join(' · ') })),
)

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  form.name_zh = props.editingCategory?.name_zh ?? ''
  form.name_en = props.editingCategory?.name_en ?? ''
  form.parent_id = props.editingCategory ? props.editingCategory.parent_id : (props.defaultParentId ?? null)
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
    parent_id: hasChildren.value ? null : form.parent_id,
    is_active: form.is_active,
  }

  try {
    const saved = props.editingCategory
      ? await updateInventoryCategory(props.editingCategory.id, payload)
      : await createInventoryCategory(payload)

    emit('update:modelValue', false)
    emit('saved', saved)
    toast.show(`Category "${payload.name_zh}" saved`)
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
    max-width="560"
    :fullscreen="display.xs.value"
    scrollable
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard :title="editingCategory ? 'Edit category' : (form.parent_id ? 'New sub-category' : 'New category')">
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
          v-if="!hasChildren"
          v-model="form.parent_id"
          :items="parentOptions"
          label="Parent category"
          hint="Leave empty for a top-level category. Max 2 levels (category › sub-category). 留空 = 頂層分類。"
          persistent-hint
          density="comfortable"
          clearable
          class="mb-3"
        />
        <VAlert
          v-else
          type="info"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          This category has sub-categories, so it cannot be placed under another category. 已有子分類，不可再放入其他分類之下。
        </VAlert>
        <VTextField
          v-model="form.name_zh"
          label="Name (Chinese)"
          hint="Required. 必填"
          persistent-hint
          density="comfortable"
          class="mb-3"
        />
        <VTextField
          v-model="form.name_en"
          label="Name (English)"
          hint="Optional. 選填"
          persistent-hint
          density="comfortable"
          class="mb-3"
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
