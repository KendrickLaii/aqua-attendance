<script setup lang="ts">
import { type CourseSpu, type CourseSpuPayload, createCourseSpu, updateCourseSpu } from '@/api/attendance/courses'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  editingSpu: CourseSpu | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')
const form = reactive({ code: '', name_zh: '', name_en: '', subject: '', description: '', is_active: true })
const canSave = computed(() => form.code.trim().length > 0 && form.name_zh.trim().length > 0)

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  const spu = props.editingSpu
  if (spu) {
    Object.assign(form, {
      code: spu.code,
      name_zh: spu.name_zh,
      name_en: spu.name_en ?? '',
      subject: spu.subject ?? '',
      description: spu.description ?? '',
      is_active: spu.is_active,
    })
  }
  else {
    Object.assign(form, { code: '', name_zh: '', name_en: '', subject: '', description: '', is_active: true })
  }
})

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''
  const payload: CourseSpuPayload = {
    code: form.code.trim(),
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    subject: form.subject.trim() || null,
    description: form.description.trim() || null,
    is_active: form.is_active,
  }
  try {
    if (props.editingSpu)
      await updateCourseSpu(props.editingSpu.id, payload)
    else
      await createCourseSpu(payload)
    emit('update:modelValue', false)
    emit('saved')
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not save course.')
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
    <VCard :title="editingSpu ? 'Edit course' : 'Add course'">
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
        <p class="text-body-2 text-medium-emphasis mb-4">
          A course is the subject family (SPU). Class offerings (SKU) sit underneath it.
        </p>
        <VRow>
          <VCol cols="6">
            <VTextField
              v-model="form.code"
              label="Code"
              placeholder="MATH"
              hint="Short unique id. Required."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.subject"
              label="Subject"
              placeholder="math"
              hint="Optional grouping label."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_zh"
              label="Chinese name"
              placeholder="小學數學"
              hint="Shown on the roster and invoices. Required."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_en"
              label="English name"
              placeholder="Primary Math"
              hint="Optional."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextarea
              v-model="form.description"
              label="Description"
              hint="Optional notes for staff. Not used for billing."
              persistent-hint
              density="comfortable"
              rows="2"
            />
          </VCol>
          <VCol cols="12">
            <VSwitch
              v-model="form.is_active"
              label="Active course"
              hint="Inactive courses stay in the list but you should not add new classes under them."
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
