<script setup lang="ts">
import {
  type ShiftTemplate,
  type ShiftTemplatePayload,
  createShiftTemplate,
  deleteShiftTemplate,
  updateShiftTemplate,
} from '@/api/attendance/shifts'
import { formatApiError } from '@/utils/formatApiDetail'
import { SHIFT_COLORS, hhmm, timeToMinutes } from '@/utils/shiftDisplay'

const props = defineProps<{
  modelValue: boolean
  templates: ShiftTemplate[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  changed: []
}>()

const saving = ref(false)
const error = ref('')
const editingId = ref<string | null>(null)
const deleteTarget = ref<ShiftTemplate | null>(null)
const deleting = ref(false)
const deleteError = ref('')

const emptyForm = () => ({ name: '', start_time: '09:00', end_time: '13:00', color: SHIFT_COLORS[0] as string })
const form = reactive(emptyForm())

const canSave = computed(() =>
  form.name.trim().length > 0
  && /^\d{2}:\d{2}$/.test(form.start_time)
  && /^\d{2}:\d{2}$/.test(form.end_time)
  && timeToMinutes(form.end_time) > timeToMinutes(form.start_time),
)

watch(() => props.modelValue, open => {
  if (open)
    resetForm()
})

function resetForm() {
  editingId.value = null
  error.value = ''
  Object.assign(form, emptyForm())
}

function edit(t: ShiftTemplate) {
  editingId.value = t.id
  error.value = ''
  Object.assign(form, { name: t.name, start_time: hhmm(t.start_time), end_time: hhmm(t.end_time), color: t.color })
}

async function save() {
  if (!canSave.value)
    return
  saving.value = true
  error.value = ''

  const payload: ShiftTemplatePayload = { ...form, name: form.name.trim() }
  try {
    if (editingId.value)
      await updateShiftTemplate(editingId.value, payload)
    else
      await createShiftTemplate({ ...payload, sort_order: props.templates.length })
    resetForm()
    emit('changed')
  }
  catch (e) {
    error.value = formatApiError(e, 'Could not save template.')
  }
  finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value)
    return
  deleting.value = true
  deleteError.value = ''
  try {
    await deleteShiftTemplate(deleteTarget.value.id)
    if (editingId.value === deleteTarget.value.id)
      resetForm()
    deleteTarget.value = null
    emit('changed')
  }
  catch (e) {
    deleteError.value = formatApiError(e, 'Could not delete template.')
  }
  finally {
    deleting.value = false
  }
}
</script>

<template>
  <VDialog
    :model-value="modelValue"
    max-width="560"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <VCard title="Shift templates">
      <VCardText>
        <p class="text-body-2 text-medium-emphasis mb-3">
          預設時間同顏色，之後一撳就排到更。改或者刪模板唔會影響已經排咗嘅更。
        </p>

        <VList
          v-if="templates.length"
          density="compact"
          class="mb-4 border rounded"
        >
          <VListItem
            v-for="t in templates"
            :key="t.id"
            :active="editingId === t.id"
          >
            <template #prepend>
              <VAvatar
                :color="t.color"
                size="16"
                class="me-3"
              />
            </template>
            <VListItemTitle>{{ t.name }}</VListItemTitle>
            <VListItemSubtitle>{{ hhmm(t.start_time) }}–{{ hhmm(t.end_time) }}</VListItemSubtitle>
            <template #append>
              <IconBtn
                size="small"
                aria-label="Edit template"
                @click="edit(t)"
              >
                <VIcon icon="ri-pencil-line" />
              </IconBtn>
              <IconBtn
                size="small"
                aria-label="Delete template"
                @click="deleteError = ''; deleteTarget = t"
              >
                <VIcon icon="ri-delete-bin-line" />
              </IconBtn>
            </template>
          </VListItem>
        </VList>
        <p
          v-else
          class="text-body-2 mb-4"
        >
          No templates yet.
        </p>

        <div class="text-subtitle-2 mb-2">
          {{ editingId ? 'Edit template' : 'New template' }}
        </div>
        <VAlert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ error }}
        </VAlert>
        <VRow>
          <VCol cols="12">
            <VTextField
              v-model="form.name"
              label="Name"
              placeholder="Morning"
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.start_time"
              type="time"
              label="Start"
              density="comfortable"
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model="form.end_time"
              type="time"
              label="End"
              density="comfortable"
            />
          </VCol>
          <VCol cols="12">
            <div class="d-flex flex-wrap gap-2">
              <VBtn
                v-for="c in SHIFT_COLORS"
                :key="c"
                :color="c"
                :variant="form.color === c ? 'flat' : 'tonal'"
                size="small"
                icon
                :aria-label="`Colour ${c}`"
                @click="form.color = c"
              >
                <VIcon
                  v-if="form.color === c"
                  icon="ri-check-line"
                />
              </VBtn>
            </div>
          </VCol>
        </VRow>
      </VCardText>
      <VCardActions>
        <VBtn
          v-if="editingId"
          variant="text"
          @click="resetForm"
        >
          Cancel edit
        </VBtn>
        <VSpacer />
        <VBtn
          variant="text"
          @click="emit('update:modelValue', false)"
        >
          Close
        </VBtn>
        <VBtn
          color="primary"
          :loading="saving"
          :disabled="!canSave"
          @click="save"
        >
          {{ editingId ? 'Save' : 'Add' }}
        </VBtn>
      </VCardActions>
    </VCard>

    <AttendanceConfirmDialog
      :model-value="!!deleteTarget"
      :title="`Delete ${deleteTarget?.name ?? 'template'}?`"
      :loading="deleting"
      :error="deleteError"
      @update:model-value="!$event && (deleteTarget = null)"
      @confirm="confirmDelete"
      @clear-error="deleteError = ''"
    >
      已經排咗嘅更會保留原本嘅時間同顏色。
    </AttendanceConfirmDialog>
  </VDialog>
</template>
