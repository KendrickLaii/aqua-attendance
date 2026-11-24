<script setup lang="ts">
import { type CourseSpu, type CourseSpuPayload, createCourseSpu, updateCourseSpu } from '@/api/attendance/courses'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import { formatApiError } from '@/utils/formatApiDetail'
import { useBranding } from '@/composables/useBranding'

const props = defineProps<{
  modelValue: boolean
  editingSpu: CourseSpu | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const { t } = useBranding()

const saving = ref(false)
const saveError = ref('')
const locations = ref<LocationItem[]>([])
const form = reactive({ location_id: '', code: '', name_zh: '', name_en: '', subject: '', description: '', is_active: true })
const canSave = computed(() => form.location_id.length > 0 && form.code.trim().length > 0 && form.name_zh.trim().length > 0)

watch(() => props.modelValue, async open => {
  if (!open)
    return
  saveError.value = ''
  if (!locations.value.length)
    locations.value = await listLocations().catch(() => [])
  const spu = props.editingSpu
  if (spu) {
    Object.assign(form, {
      location_id: spu.location_id,
      code: spu.code,
      name_zh: spu.name_zh,
      name_en: spu.name_en ?? '',
      subject: spu.subject ?? '',
      description: spu.description ?? '',
      is_active: spu.is_active,
    })
  }
  else {
    Object.assign(form, { location_id: locations.value.length === 1 ? locations.value[0].id : '', code: '', name_zh: '', name_en: '', subject: '', description: '', is_active: true })
  }
})

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  saveError.value = ''
  const payload: CourseSpuPayload = {
    location_id: form.location_id,
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
    saveError.value = formatApiError(e, `Could not save ${t('course')}.`)
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
    <VCard :title="editingSpu ? t('Edit course') : t('Add course')">
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
          A {{ t('course') }} is the subject family (SPU). {{ t('Class offerings') }} (SKU) sit underneath it.
        </p>
        <VRow>
          <VCol cols="12">
            <VSelect
              v-model="form.location_id"
              :items="locations"
              item-title="name_en"
              item-value="id"
              :label="t('location')"
              :hint="`Only this ${t('location')} can see and edit this ${t('course')}. A new ${t('location')} starts with an empty list.`"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.code"
              label="Code"
              placeholder="MATH"
              :hint="`Short id, unique inside this ${t('location')}. Required.`"
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.subject"
              :label="t('Subject')"
              placeholder="math"
              hint="Optional grouping label."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_zh"
              :label="t('Chinese name')"
              placeholder="小學數學"
              hint="Shown on the roster and invoices. Required."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_en"
              :label="t('English name')"
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
              :label="t('Active course')"
              :hint="`Inactive ${t('courses')} stay in the list but you should not add new ${t('classes')} under them.`"
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
