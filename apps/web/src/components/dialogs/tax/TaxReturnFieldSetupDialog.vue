<script setup lang="ts">
import type {
  ApiTemplate,
  ApiTemplateRequest,
  TemplateField,
  TemplateFormData,
} from '@/types/tax-return-field-setup'
import { parseContentToFields } from '@/types/tax-return-field-setup'
import type { VForm } from 'vuetify/components/VForm'
import {
  createTaxReturnFieldSetup,
  updateTaxReturnFieldSetup,
} from '@/api/tax-return-field-setup'
import ConfirmDialog from '@/components/dialogs/tax/ConfirmDialog.vue'

/**
 * Transform form data to API request format
 * Filters out empty fields and wraps them in content object
 */
function formDataToPayload(formData: TemplateFormData): ApiTemplateRequest {
  // Remove empty fields
  const validFields = formData.fields.filter(field => field.name)

  // Build API request payload
  const payload: ApiTemplateRequest = {
    title: formData.title,
    description: formData.description,
    year: formData.year,
    status: formData.status,
    content: { fields: validFields },
  }

  // Add UUID only for edit mode (when it exists)
  if (formData.uuid) {
    payload.uuid = formData.uuid
  }

  return payload
}

interface Emit {
    (e: 'update:isDialogVisible', value: boolean): void
    (e: 'success'): void
    (e: 'showAlert', message: string): void
}

const emit = defineEmits<Emit>()

const isDialogVisible = ref(false)
const dialogMode = ref<'Create' | 'Edit'>('Create')
const formRef = ref<VForm>()

const defaultField = (): TemplateField => ({
  name: '',
  type: null,
  aqua_mapping: '',
  ird_mapping: '',
  tax_return_number: '',
  tax_return_reference: '',
})

//form initial
const formData = ref<TemplateFormData>({
    title: '',
    description: '',
    year: '',
    status: 'enable',
    fields: [defaultField()],
})

// Year picker state management
// We maintain two separate values:
// 1. selectedYearDate: Date object for VDatePicker to highlight the correct year
// 2. formData.year: Formatted string (e.g., "2025/26") for display and API
const isDatePickerOpen = ref(false)
const selectedYearDate = ref<Date | undefined>(undefined)

// Handle year selection from date picker
// Converts selected year to fiscal year format (YYYY/YY)
// Example: selecting 2025 → displays "2025/26"
const onYearSelect = (year: number) => {
    // Store as Date object for picker to maintain selection state
    selectedYearDate.value = new Date(year, 0, 1)
    
    // Format year as fiscal year (e.g., 2025 → "2025/26")
    const nextYear = (year + 1).toString().slice(-2) // Get last 2 digits of next year
    formData.value.year = `${year}/${nextYear}`
    
    isDatePickerOpen.value = false
  }

const formValidated = ref(false)

// for create
const getDefaultFormData = (): TemplateFormData => ({
  title: '',
  description: '',
  year: '',
  status: 'enable',
  fields: [defaultField()],
})
// for edit
const populateFormFromTemplate = (template: ApiTemplate): TemplateFormData => {
  const raw = parseContentToFields(template.content)
  const fields: TemplateField[] = (raw.length > 0 ? raw : [defaultField()]).map(f => ({
    name: f.name ?? '',
    type: f.type ?? null,
    aqua_mapping: f.aqua_mapping ?? '',
    ird_mapping: f.ird_mapping ?? '',
    tax_return_number: f.tax_return_number ?? '',
    tax_return_reference: f.tax_return_reference ?? '',
  }))
  return {
    title: template.title ?? '',
    description: template.description ?? '',
    year: template.year ?? '',
    status: template.status ?? 'enable',
    uuid: template.uuid,
    fields: fields.length > 0 ? fields : [{ name: '', type: null }],
  }
}

const openDialog = (mode: 'Create' | 'Edit', data: ApiTemplate | null = null) => {
  isDialogVisible.value = true
  dialogMode.value = mode

  if (mode === 'Edit' && data) {
    formData.value = populateFormFromTemplate(data)
    
    // Parse fiscal year format back to Date object for picker
    // Example: "2025/26" → extract "2025" → new Date(2025, 0, 1)
    // This ensures the date picker highlights the correct year when editing
    const yearMatch = formData.value.year.match(/^(\d{4})/)
    selectedYearDate.value = yearMatch ? new Date(parseInt(yearMatch[1]), 0, 1) : undefined
  } else {
    // Reset to default state for create mode
    formData.value = getDefaultFormData()
    selectedYearDate.value = undefined
    formValidated.value = false
    formRef.value?.resetValidation()
  }
}

/**
 * Expose methods to parent component
 * Usage in parent:
 * 1. Create ref: const dialogRef = ref<InstanceType<typeof TaxReturnFieldSetupDialog>>()
 * 2. Bind to template: <TaxReturnFieldSetupDialog ref="dialogRef" />
 * 3. Call exposed method: dialogRef.value?.openDialog('Create', null)
 */
defineExpose({
  openDialog
})
const deleteItemIndex = ref<number | null>(null)
const showDeleteConfirm = ref<boolean>(false)

const showDeleteDialog = (index: number) => {
  if (formData.value.fields.length > 1) {
    deleteItemIndex.value = index
    showDeleteConfirm.value = true
  } else {
    emit('showAlert', 'You must have at least one field')
  }
}

const confirmDelete = async () => {
  if (deleteItemIndex.value === null) return
  try {
    removeField(deleteItemIndex.value)
    emit('showAlert', 'Field deleted successfully')
  } catch (error) {
    emit('showAlert', 'Failed to delete field')
  } finally {
    deleteItemIndex.value = null
    showDeleteConfirm.value = false
  }
}

const cancelDelete = () => {
  deleteItemIndex.value = null
  showDeleteConfirm.value = false
}

const submitTaxReturnFieldSetup = async (closeAfterSave = true) => {
  formValidated.value = true
  const validation = await formRef.value?.validate()
  const isValid = validation?.valid || false

  if (!isValid) return

  try {
    const payload = formDataToPayload(formData.value)
    
    if (dialogMode.value === 'Create') {
      const res = await createTaxReturnFieldSetup(payload)
      console.log('Create response:', res)
      emit('showAlert', 'Tax return field setup created successfully')
    } else if (dialogMode.value === 'Edit') {
      const res = await updateTaxReturnFieldSetup(payload)
      console.log('Update response:', res)
      emit('showAlert', 'Tax return field setup updated successfully')
    }
    
    emit('success')
    if (closeAfterSave)
      isDialogVisible.value = false
  } catch (error) {
    console.error('Failed to save tax return field setup:', error)
    emit('showAlert', `Failed to save template: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

const saveTaxReturnFieldSetup = async () => {
  await submitTaxReturnFieldSetup(false)
}

// cancel button or close button
const resetData = () => {
  isDialogVisible.value = false
  
  nextTick(() => {
    formData.value = {
      title: '',
      description: '',
      year: '',
      status: 'enable',
      fields: [defaultField()],
    }
    formValidated.value = false
    formRef.value?.resetValidation()
  })
}

// === Field handle ===
const addField = () => {
  formData.value.fields.push(defaultField())
}

const removeField = (index: number) => {
  if (formData.value.fields.length > 1) {
    formData.value.fields.splice(index, 1)
  } else {
    emit('showAlert', 'You must have at least one field')
  }
}

// === Row reordering / inserting ===
const moveFieldUp = (index: number) => {
  if (index <= 0) return
  const fields = formData.value.fields
  ;[fields[index - 1], fields[index]] = [fields[index], fields[index - 1]]
}

const moveFieldDown = (index: number) => {
  const fields = formData.value.fields
  if (index >= fields.length - 1) return
  ;[fields[index], fields[index + 1]] = [fields[index + 1], fields[index]]
}

const insertFieldAbove = (index: number) => {
  formData.value.fields.splice(index, 0, defaultField())
}

const insertFieldBelow = (index: number) => {
  formData.value.fields.splice(index + 1, 0, defaultField())
}
</script>
    
<template>
    <VDialog
    scrollable
    :width="$vuetify.display.smAndDown ? 'auto' : 1400"
    v-model="isDialogVisible"
    >
    <VCard class="pa-sm-6 pa-4">
        <div class="d-flex justify-space-between align-center mb-4">
            <h5 class="text-h5">
                {{ dialogMode === 'Create' ? 'Add New Tax Return Field Setup' : 'Edit Tax Return Field Setup' }}
            </h5>
            <!-- 👉 dialog close btn -->
            <DialogCloseBtn
                variant="text"
                size="default"
                @click="resetData"
            />
        </div>

        <VDivider />
        
        <VCardText class="pt-4">
            <!-- {{ formData }} -->
        <VForm ref="formRef" @submit.prevent="">
            <VRow>
            <!-- 👉 Title -->
            <VCol cols="6">
                <VTextField
                hide-details
                v-model="formData.title"
                label="Title"
                placeholder="Enter Title"
                density="compact"
                :rules="[requiredValidator]"
                class="required-field"
                />
            </VCol>

            <!-- 👉 Year -->
            <VCol cols="6">
              <!-- Date picker -->
              <!-- <VMenu v-model="isDatePickerOpen" :close-on-content-click="false">
                <template #activator="{ props }">
                  <VTextField class="required-field" hide-details density="compact" v-bind="props" :model-value="formData.year" label="Year" readonly :rules="[requiredValidator]" required />
                </template>
                <VDatePicker
                  class="year-picker"
                  hide-header
                  view-mode="year"
                  :model-value="selectedYearDate"
                  @update:year="onYearSelect"
                  
                />
              </VMenu> -->
              
              <!-- Manual year input -->
              <VTextField
                v-model="formData.year"
                class="required-field"
                hide-details
                density="compact"
                label="Year"
                placeholder="e.g., 2025/26"
                :rules="[requiredValidator]"
                required
              />
            </VCol>

            <!-- 👉 Description -->
            <VCol cols="12">
                <VTextField
                    hide-details
                    v-model="formData.description"
                    label="Description"
                    placeholder="Enter Description"
                    density="compact"
                />
            </VCol>

            <VDivider />
            <!-- 👉 Fields -->
            <template v-for="(field, index) in formData.fields" :key="index">
                <VCol cols="12">
                    <div class="d-flex gap-2 align-center field-row">
                        <VMenu location="bottom start">
                            <template #activator="{ props: menuProps }">
                                <VBtn
                                    v-bind="menuProps"
                                    icon="ri-more-2-fill"
                                    variant="text"
                                    size="small"
                                    density="compact"
                                    class="row-actions-btn"
                                />
                            </template>
                            <VList density="compact" min-width="200">
                                <VListItem
                                    :disabled="index === 0"
                                    @click="moveFieldUp(index)"
                                >
                                    <template #prepend>
                                        <VIcon icon="ri-arrow-up-line" size="18" />
                                    </template>
                                    <VListItemTitle>Move up</VListItemTitle>
                                </VListItem>
                                <VListItem
                                    :disabled="index === formData.fields.length - 1"
                                    @click="moveFieldDown(index)"
                                >
                                    <template #prepend>
                                        <VIcon icon="ri-arrow-down-line" size="18" />
                                    </template>
                                    <VListItemTitle>Move down</VListItemTitle>
                                </VListItem>
                                <VDivider class="my-1" />
                                <VListItem @click="insertFieldAbove(index)">
                                    <template #prepend>
                                        <VIcon icon="ri-insert-row-top" size="18" />
                                    </template>
                                    <VListItemTitle>Insert row above</VListItemTitle>
                                </VListItem>
                                <VListItem @click="insertFieldBelow(index)">
                                    <template #prepend>
                                        <VIcon icon="ri-insert-row-bottom" size="18" />
                                    </template>
                                    <VListItemTitle>Insert row below</VListItemTitle>
                                </VListItem>
                            </VList>
                        </VMenu>
                        <VTextField
                            hide-details
                            v-model="formData.fields[index].tax_return_number"
                            label="Tax return no."
                            placeholder="Tax return no."
                            density="compact"
                            style="flex: 0 1 160px"
                            :rules="[requiredValidator]"
                            class="required-field"
                        />
                        <VTextField
                            hide-details
                            v-model="formData.fields[index].name"
                            :label="`Field Name ${index + 1}`"
                            placeholder="Enter Field Name"
                            density="compact"
                            :rules="[requiredValidator]"
                            class="required-field"
                            style="flex: 1 1 40%"
                        />
                        <VSelect
                            hide-details
                            v-model="formData.fields[index].type"
                            label="Field Type"
                            placeholder="Select Field Type"
                            density="compact"
                            :items="['text', 'integer', 'date', 'radio']"
                            :rules="[requiredValidator]"
                            class="required-field"
                            style="flex: 0 1 200px"
                        />
                        <VTextField
                            hide-details
                            v-model="formData.fields[index].tax_return_reference"
                            label="Tax return ref."
                            placeholder="Tax return ref."
                            density="compact"
                            style="flex: 0 1 160px"
                            :rules="[requiredValidator]"
                            class="required-field"
                        />
                        <VTextField
                            hide-details
                            v-model="formData.fields[index].ird_mapping"
                            label="IRD mapping"
                            placeholder="IRD mapping"
                            density="compact"
                            style="flex: 0 1 160px"
                            :rules="[requiredValidator]"
                            class="required-field"
                        />
                        <VTextField
                            hide-details
                            v-model="formData.fields[index].aqua_mapping"
                            label="Aqua mapping"
                            placeholder="Aqua mapping"
                            density="compact"
                            style="flex: 0 1 160px"
                        />
                        <VBtn
                            class="mt-1"
                            size="x-small"
                            variant="elevated"
                            color="error"
                            icon="ri-delete-bin-5-line"
                            @click="showDeleteDialog(index)"
                        >
                        </VBtn>
                    </div>
                </VCol>
            </template>
            <VCol cols="12" class="d-flex align-center justify-center">
                <VBtn
                    size="small"
                    variant="elevated"
                    color="primary"
                    @click="addField"
                >
                    <VIcon
                        icon="ri-add-line"
                        class="flip-in-rtl"
                    />Add Field 
                </VBtn>
            </VCol>
            </VRow>
        </VForm>
        </VCardText>
        <V-Divider />
        <!-- 👉footer buttons -->
        <VCardActions class="d-flex justify-end flex-wrap gap-4 py-3 px-3">
            <VBtn
                color="secondary"
                variant="outlined"
                @click="resetData"
            >
                Close
            </VBtn>

            <VBtn
                v-if="dialogMode === 'Edit'"
                variant="elevated"
                color="primary"
                @click="saveTaxReturnFieldSetup"
            >
                Save
            </VBtn>

            <VBtn
                type="submit"
                variant="elevated"
                color="primary"
                @click="submitTaxReturnFieldSetup"
            >
                {{dialogMode === 'Create' ? 'Submit' : 'Save and Close'}}
                <VIcon
                    end
                    icon="ri-check-line"
                    class="flip-in-rtl"
                />
            </VBtn>
        </VCardActions>
    </VCard>
    </VDialog>
    <!-- 👉 delete confirmation dialog -->
    <ConfirmDialog
        v-model="showDeleteConfirm"
        header="Confirm Delete"
        text="Are you sure you want to delete this field?<br/>This action cannot be undone."
        confirm-button-text="Delete"
        confirm-button-color="error"
        max-width="500"
        use-html
        @confirm="confirmDelete"
        @cancel="cancelDelete"
    />
</template>
<style lang="scss" scoped>
.required-field :deep(.v-field__field label::before),
.required-field :deep(.v-label::before) {
  content: "*";
  color: rgb(var(--v-theme-error));
  margin-left: 1px;
}
:deep(.v-col){
    padding-bottom: 6px !important;
}

// date picker 
.year-picker {
 :deep(.v-date-picker-controls){
    display: none;
 }
 :deep(.v-date-picker-years){
  margin-top: 1rem;
 }
}

.field-row {
  border-radius: 4px;
  padding: 4px;
  margin: -4px;
}

.row-actions-btn {
  color: rgba(var(--v-theme-on-surface), 0.5);

  &:hover {
    color: rgba(var(--v-theme-on-surface), 0.9);
  }
}
</style>
