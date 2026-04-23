<script setup lang="ts">
import type { Content } from '@/types/administrator'
import type { VForm } from 'vuetify/components/VForm'
import { createAdministrator, updateAdministrator } from '@api/administrator'

export interface AdministratorFormData {
    username: string
    role: string
    status: string
    uuid?: string
    password: string
}

interface Emit {
    (e: 'update:isDialogVisible', value: boolean): void
    (e: 'success'): void
    (e: 'showAlert', message: string): void
}

const emit = defineEmits<Emit>()

const isDialogVisible = ref(false)
const dialogMode = ref<'Create' | 'Edit'>('Create')
const passwordVisible = ref(false)
const formRef = ref<VForm>()
const roleOptions = ref([
    { value: 'admin', label: 'Admin' },
    { value: 'staff', label: 'Staff' },
])

//form initial
const formData = ref<AdministratorFormData>({
    username: '',
    role: '',
    status: 'enable',
    password: '',
})

const hasRoleError = computed(() => {
  // Show error if field is empty and form has been validated (and validation failed)
  return !formData.value.role && formValidated.value
})

const formValidated = ref(false)

const openDialog = (mode: 'Create' | 'Edit', data: Content | null = null) => {
    isDialogVisible.value = true
    dialogMode.value = mode
    if (mode === 'Edit' && data) {
        formData.value = {
            username: data.username || '',
            role: data.role || '',
            status: data.status || 'enable',
            password: '', // Don't populate password for security
            uuid: data.uuid,
        }
    } else {
        formData.value = {
            username: '',
            role: '',
            status: 'enable',
            password: '',
        }
        formValidated.value = false
        formRef.value?.resetValidation()
    }
}

// Expose method to parent component
defineExpose({
  openDialog
})

const formSubmit = async () => {
    formValidated.value = true
    const validation = await formRef.value?.validate()
    const isValid = validation?.valid || false
    
    if (isValid) {
        try {
            if (dialogMode.value === 'Create') {
                await createAdministrator(formData.value)
                emit('showAlert', 'Administrator created successfully')
            } else if (dialogMode.value === 'Edit') {
                await updateAdministrator(formData.value)
                emit('showAlert', 'Administrator updated successfully')
            }
            emit('success')
            isDialogVisible.value = false
        } catch (error) {
            console.error('Failed to save administrator:', error)
        }
    } else {
        console.log('Form is invalid')
    }
}

const resetData = () => {
  // Close dialog - this will unmount all tab components due to v-if
  isDialogVisible.value = false
  
  // Reset data after dialog is closed
  nextTick(() => {
    formData.value = {
      username: '',
      role: '',
      status: 'enable',
      password: '',
    }
    formValidated.value = false
    formRef.value?.resetValidation()
    passwordVisible.value = false
  })
}
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
                {{ dialogMode === 'Create' ? 'Add New Administrator' : 'Edit Administrator' }}
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
            <!-- 👉 ID -->
            <VCol cols="12">
                <VTextField
                v-model="formData.username"
                label="ID"
                placeholder="Enter ID"
                hide-details
                :rules="[requiredValidator]"
                class="required-field"
                />
            </VCol>

            <!-- 👉 Password -->
            <VCol cols="12">
                <VTextField
                    v-model="formData.password"
                    label="Password"
                    placeholder="Enter Password"
                    density="compact"
                    hide-details
                    :rules="[requiredValidator]"
                    class="required-field"
                    :append-inner-icon="passwordVisible ? 'ri-eye-off-line' : 'ri-eye-line'"
                    :type="passwordVisible ? 'text' : 'password'"
                    @click:append-inner="passwordVisible = !passwordVisible"
                />
            </VCol>

            <VCol cols="12">
                <VRadioGroup
                    v-model="formData.role"
                    label="Role"
                    :rules="[requiredValidator]"
                    inline
                    class="role-radio-group"
                    :class="{ 'field-error': hasRoleError }"
                >
                    <VRadio 
                        v-for="option in roleOptions"
                        :key="option.value"
                        :value="option.value"
                        :label="option.label"
                    />
                </VRadioGroup>
            </VCol>
            </VRow>
        </VForm>
        </VCardText>
        <V-Divider />
        <!-- 👉footer buttons -->
        <VCardText class="overflow-hidden d-flex justify-end flex-wrap gap-4 pt-3 pb-1 px-4">
            <VBtn
            color="secondary"
            variant="outlined"
            @click="resetData"
            >
            Cancel
            </VBtn>

            <VBtn
            type="submit"
            @click="formSubmit"
            >
            Submit
            <VIcon
                end
                icon="ri-check-line"
                class="flip-in-rtl"
            />
            </VBtn>
        </VCardText>
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
/* Increase gap between occupation radio buttons */
.role-radio-group {
  border: 1px solid #d1cfd4;
  border-radius: .5rem;
  padding: .5rem;
  &:deep(.v-selection-control-group){
    gap: 1rem !important;
  }
}

/* Error state: red border */
.role-radio-group.field-error {
  border-color: rgb(var(--v-theme-error)) !important;
  
  /* radiogroup icon and label */
  &:deep(.v-selection-control__input > .v-icon),
  &:deep(.v-label){
    color: rgb(var(--v-theme-error)) !important;
  }
}
</style>
