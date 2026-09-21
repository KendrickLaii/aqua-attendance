<script setup lang="ts">
import {
  type BillingUnit,
  type CourseSku,
  type CourseSkuPayload,
  type Weekday,
  createCourseSku,
  updateCourseSku,
} from '@/api/attendance/courses'
import { billingUnitOptions, skuBillingPreview, weekdayOptions } from '@/utils/courseRosterDisplay'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  modelValue: boolean
  editingSku: CourseSku | null
  selectedSpuId: string | null
  locationOptions: { id: string; title: string }[]
  staffOptions: { value: string; title: string }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const saving = ref(false)
const saveError = ref('')
const form = reactive({
  code: '',
  name_zh: '',
  name_en: '',
  level: '',
  schedule_note: '',
  location_id: null as string | null,
  staff_id: null as string | null,
  capacity: null as number | null,
  price: null as number | null,
  billing_unit: 'monthly' as BillingUnit,
  meeting_weekdays: [] as Weekday[],
  is_active: true,
})

const canSave = computed(() => !!(form.code.trim() && form.name_zh.trim()))
const billingPreview = computed(() => skuBillingPreview(form.billing_unit, form.price))

function resetForm(sku: CourseSku | null) {
  if (sku) {
    Object.assign(form, {
      code: sku.code,
      name_zh: sku.name_zh,
      name_en: sku.name_en ?? '',
      level: sku.level ?? '',
      schedule_note: sku.schedule_note ?? '',
      location_id: sku.location_id,
      staff_id: sku.staff_id,
      capacity: sku.capacity,
      price: sku.price,
      billing_unit: sku.billing_unit,
      meeting_weekdays: [...(sku.meeting_weekdays ?? [])],
      is_active: sku.is_active,
    })
    return
  }
  Object.assign(form, {
    code: '',
    name_zh: '',
    name_en: '',
    level: '',
    schedule_note: '',
    location_id: null,
    staff_id: null,
    capacity: null,
    price: null,
    billing_unit: 'monthly' as BillingUnit,
    meeting_weekdays: [] as Weekday[],
    is_active: true,
  })
}

watch(() => props.modelValue, open => {
  if (!open)
    return
  saveError.value = ''
  resetForm(props.editingSku)
})

async function save() {
  if (!props.selectedSpuId || !canSave.value)
    return
  saving.value = true
  saveError.value = ''
  const payload: CourseSkuPayload = {
    spu_id: props.selectedSpuId,
    code: form.code.trim(),
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    level: form.level.trim() || null,
    schedule_note: form.schedule_note.trim() || null,
    location_id: form.location_id,
    staff_id: form.staff_id,
    capacity: form.capacity,
    price: form.price,
    billing_unit: form.billing_unit,
    meeting_weekdays: form.meeting_weekdays,
    is_active: form.is_active,
  }
  try {
    if (props.editingSku)
      await updateCourseSku(props.editingSku.id, payload)
    else
      await createCourseSku(payload)
    emit('update:modelValue', false)
    emit('saved')
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Could not save class offering.')
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
    <VCard :title="editingSku ? 'Edit class' : 'Add class'">
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
        <VAlert
          type="info"
          variant="tonal"
          density="compact"
          class="mb-4"
        >
          {{ billingPreview }}
        </VAlert>

        <div class="text-subtitle-2 mb-2">
          Identity
        </div>
        <VRow>
          <VCol cols="6">
            <VTextField
              v-model="form.code"
              label="Class code"
              placeholder="MATH-P3-TUE"
              hint="Unique. Required."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.level"
              label="Level"
              placeholder="P3"
              hint="Optional, e.g. P3 / F5 / A1."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VTextField
              v-model="form.name_zh"
              label="Chinese name"
              placeholder="小學數學 P3 週二班"
              hint="Shown on invoices. Required."
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
        </VRow>

        <div class="text-subtitle-2 mt-4 mb-2">
          When and where
        </div>
        <VRow>
          <VCol cols="12">
            <VTextField
              v-model="form.schedule_note"
              label="Time note"
              placeholder="Tue 18:00–19:30"
              hint="For staff display only. Not used for billing."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="form.location_id"
              :items="locationOptions"
              item-title="title"
              item-value="id"
              label="Campus"
              hint="Display only. Invoices filter by each student's registered campus, not this."
              persistent-hint
              density="comfortable"
              clearable
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VAutocomplete
              v-model="form.staff_id"
              :items="staffOptions"
              label="Teacher / staff"
              hint="Optional. The staff member who teaches this class."
              persistent-hint
              density="comfortable"
              clearable
            />
          </VCol>
          <VCol
            cols="12"
            sm="4"
          >
            <VTextField
              v-model.number="form.capacity"
              label="Capacity"
              type="number"
              min="0"
              hint="Roster size only. Not billed."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol
            cols="12"
            sm="8"
          >
            <div class="text-body-2 mb-1">
              Class days
            </div>
            <div class="text-caption text-medium-emphasis mb-2">
              Optional. Shown on the roster for reference only; not used to calculate the bill.
            </div>
            <VChipGroup
              v-model="form.meeting_weekdays"
              multiple
              selected-class="text-primary"
            >
              <VChip
                v-for="day in weekdayOptions"
                :key="day.value"
                :value="day.value"
                filter
                variant="outlined"
                size="small"
              >
                {{ day.title }}
              </VChip>
            </VChipGroup>
          </VCol>
        </VRow>

        <div class="text-subtitle-2 mt-4 mb-2">
          Billing
        </div>
        <VRow>
          <VCol cols="6">
            <VSelect
              v-model="form.billing_unit"
              :items="billingUnitOptions"
              item-title="title"
              item-value="value"
              label="How this class is charged"
              hint="One method per class."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model.number="form.price"
              :label="form.billing_unit === 'per_session' ? 'Price per session' : 'Monthly price'"
              type="number"
              min="0"
              step="0.01"
              prefix="HK$"
              hint="Leave empty to skip this class at Generate — or for variable-rate classes like 私補, leave empty and set a per-student price on each enrollment."
              persistent-hint
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <VSwitch
              v-model="form.is_active"
              label="Active class"
              hint="Off: hidden from new enrollments and skipped at Generate. Issued/paid bills stay."
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
