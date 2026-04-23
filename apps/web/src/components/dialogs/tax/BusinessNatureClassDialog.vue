<script setup lang="ts">
import {
  createBusinessNature,
  updateBusinessNature,
} from '@/api/business-nature'
import type { BusinessNatureItem, BusinessNaturePayload } from '@/types/business-nature'
import type { VForm } from 'vuetify/components/VForm'

// 👉 Form data interface
export interface FormData {
  uuid?: string
  businessNature: string
  hsicCode: string
  hsicClassification: string
  status: 'enable' | 'disable'
}

// 👉 Emit interface
interface Emit {
  (e: 'showAlert', value: string): void
  (e: 'saved'): void
}
// 👉 Emit
const emit = defineEmits<Emit>()

const isDialogVisible = ref(false)
const dialogMode = ref<'Create' | 'Edit'>('Create')
const businessNatureClassData = ref<BusinessNatureItem | null>(null)
const formRef = ref<VForm>()
const isSubmitting = ref(false)

// 👉Dropdown items
const statusItems = [
    { title: 'Enable', value: 'enable' },
    { title: 'Disable', value: 'disable' },
]
const formValidated = ref(false)
// 👉 Form initial data
const formData = ref<FormData>({
  businessNature: '',
  hsicCode: '',
  hsicClassification: '',
  status: 'enable',
})
// 👉 Method to open dialog - exposed to parent component
const openDialog = async (mode: 'Create' | 'Edit', data: BusinessNatureItem | null = null) => {
  dialogMode.value = mode
  businessNatureClassData.value = data
  
  if (mode === 'Edit' && data) {
    formData.value = {
      uuid: data.uuid,
      businessNature: data.business_nature || '',
      hsicCode: data.hsic_code || '',
      hsicClassification: data.hsic_classification || '',
      status: data.status || 'enable',
    }
  } else {
    formData.value = {
      businessNature: '',
      hsicCode: '',
      hsicClassification: '',
      status: 'enable',
    }
    formValidated.value = false
    formRef.value?.resetValidation()
  }
  
  // Open dialog - components will mount due to v-if
  isDialogVisible.value = true
}

const mapToApiPayload = (): BusinessNaturePayload => ({
  business_nature: formData.value.businessNature,
  hsic_code: formData.value.hsicCode,
  hsic_classification: formData.value.hsicClassification,
  status: formData.value.status,
})

// 👉 Form submission: validate then call API by dialogMode.
const formSubmit = async () => {
  if (isSubmitting.value) return

  formValidated.value = true
  const validation = await formRef.value?.validate()
  const isValid = validation?.valid ?? false

  if (!isValid) {
    emit('showAlert', 'Please fill in all required fields to save business nature class')
    return
  }

  try {
    isSubmitting.value = true
    const payload = mapToApiPayload()

    if (dialogMode.value === 'Create') {
      await createBusinessNature(payload)
      emit('showAlert', 'Business nature class created successfully')
    }
    else {
      if (!formData.value.uuid) {
        emit('showAlert', 'Missing uuid for edit')
        return
      }
      await updateBusinessNature(formData.value.uuid, payload)
      emit('showAlert', 'Business nature class updated successfully')
    }

    emit('saved')
    resetData()
  } catch (error) {
    console.error('Failed to save business nature class:', error)
    emit('showAlert', 'Failed to save business nature class')
  } finally {
    isSubmitting.value = false
  }
}

// 👉 Reset data
const resetData = () => {
  // Close dialog - this will unmount all tab components due to v-if
  isDialogVisible.value = false
  
  // 👉 Reset data after dialog is closed
  nextTick(() => {
    businessNatureClassData.value = null
    formData.value = {
      businessNature: '',
      hsicCode: '',
      hsicClassification: '',
      status: 'enable',
    }
    formValidated.value = false
    formRef.value?.resetValidation()
  })
}

// 👉 Method to browse HSIC
const browseHSIC = (keyword: string) => {
    if(!keyword) {
        emit('showAlert', 'Please enter a business nature to browse HSIC')
        return
    }
    window.open(`https://www.censtatd.gov.hk/en/index_hsic2_code.html?keyword=${encodeURIComponent(keyword)}`, '_blank')
}

// 👉 Expose methods to parent component
defineExpose({
  openDialog,
  closeDialog: resetData,
})
</script>

<template>
  <VDialog
    scrollable
    :width="$vuetify.display.smAndDown ? 'auto' : 600"
    v-model="isDialogVisible"
    >
    <VCard class="pa-sm-6 pa-4">
        <div class="d-flex justify-space-between align-center mb-4">
            <h5 class="text-h5">
                {{ dialogMode === 'Create' ? 'Add New Business Nature Class' : 'Edit Business Nature Class' }}
            </h5>
            <!-- 👉 dialog close btn -->
            <DialogCloseBtn
                variant="text"
                size="default"
                @click="resetData"
            />
        </div>

        <VDivider />
        
        <VCardText class="pt-5">

        <VForm ref="formRef" @submit.prevent="">
            <VRow>
            <!-- 👉 Business Nature -->
            <VCol cols="12">
                <VTextField
                v-model="formData.businessNature"
                label="Business Nature"
                hide-details
                placeholder="Enter Business Nature"
                density="compact"
                :rules="[requiredValidator]"
                class="required-field"
                />
                <small class="cursor-pointer ml-2" @click="browseHSIC(formData.businessNature)">
                    <span :style="$vuetify.theme.name === 'dark' ? 'color: white' : 'color: blue'">
                        <u>Browse from Hong Kong Standard Industrial Classification</u>
                    </span>
                </small>
            </VCol>

            <!-- 👉 HSIC Code -->
            <VCol cols="12">
                <VTextField
                    v-model="formData.hsicCode"
                    label="HSIC Code"
                    placeholder="Enter HSIC Code"
                    density="compact"
                />
            </VCol>

            <!-- 👉 HSIC Classification -->
            <VCol cols="12">
                <VTextField
                    v-model="formData.hsicClassification"
                    label="HSIC Classification"
                    placeholder="Enter HSIC Classification"
                    density="compact"
                />
            </VCol>
            <!-- 👉 Status Dropdown -->
            <VCol cols="12">
                <VSelect
                    v-model="formData.status"
                    :items="statusItems"
                    label="Status"
                    placeholder="Select Status"
                    density="compact"
                    hide-details
                    class="required-field"
                    :rules="[requiredValidator]"
                />
            </VCol>
            </VRow>
        </VForm>
        </VCardText>
        <V-Divider />
        <!-- 👉 Footer buttons -->
        <VCardActions class="d-flex justify-end flex-wrap gap-4 py-3 px-3">
            <VBtn
                color="secondary"
                variant="outlined"
                @click="resetData"
            >
                Cancel
            </VBtn>

            <VBtn
                type="submit"
                variant="elevated"
                color="primary"
                @click="formSubmit"
            >
                    Submit
                <VIcon
                    end
                    icon="ri-check-line"
                    class="flip-in-rtl"
                />
            </VBtn>
        </VCardActions>
    </VCard>
    </VDialog>
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
</style>
