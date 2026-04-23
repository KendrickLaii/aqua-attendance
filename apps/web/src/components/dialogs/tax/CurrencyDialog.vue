<script setup lang="ts">
import type { CurrencyProperties } from '@/types/currency'
import type { VForm } from 'vuetify/components/VForm'

// 👉 Form data interface
export interface FormData {
    id?: number
    uuid?: string
    currency: string
    currency_symbol: string
    exchange_rate: string
    status: 'enable' | 'disable'
}

// 👉 Emit interface
interface Emit {
  (e: 'create', value: FormData): void
  (e: 'edit', value: FormData & { id: number }): void
  (e: 'showAlert', value: string): void
}
// 👉 Emit
const emit = defineEmits<Emit>()

const isDialogVisible = ref(false)
const dialogMode = ref<'Create' | 'Edit'>('Create')
const currencyData = ref<CurrencyProperties | null>(null)
const formRef = ref<VForm>()

// 👉Dropdown items
const statusItems = [
    { title: 'Enable', value: 'enable' },
    { title: 'Disable', value: 'disable' },
]

const formValidated = ref(false)
const exchangeRateValidator = (v: string | number) => {
  const s = String(v ?? '').trim()
  if (!s)
    return 'Exchange Rate is required'
  return /^\d+(\.\d{1,2})?$/.test(s) || 'Maximum 2 decimal places allowed'
}
// 👉 Form initial data
const formData = ref<FormData>({
    currency: '',
    currency_symbol: '',
    exchange_rate: '',
    status: 'enable',
})
// 👉 Method to open dialog - exposed to parent component
const openDialog = async (mode: 'Create' | 'Edit', data: CurrencyProperties | null = null) => {
  dialogMode.value = mode
  currencyData.value = data
  
  if (mode === 'Edit' && data) {
    formData.value = {
      id: data.id,
      uuid: data.uuid,
      currency: data.currency || '',
      currency_symbol: data.currency_symbol || '',
      exchange_rate: String(data.exchange_rate ?? ''),
      status: data.status || 'enable',
    }
  } else {
    formData.value = {
      currency: '',
      currency_symbol: '',
      exchange_rate: '',
      status: 'enable',
    }
    formValidated.value = false
    formRef.value?.resetValidation()
  }
  
  // Open dialog - components will mount due to v-if
  isDialogVisible.value = true
}

// 👉 Form submission: validate then emit create or edit by dialogMode; parent performs API and closes dialog.
const formSubmit = async () => {
  formValidated.value = true
  const validation = await formRef.value?.validate()
  const isValid = validation?.valid ?? false

  if (!isValid) {
    emit('showAlert', 'Please fill in all required fields to save currency')
    return
  }

  const payload = { ...formData.value }
  if (dialogMode.value === 'Create')
    emit('create', payload)
  else if (formData.value.id != null)
    emit('edit', payload as FormData & { id: number })
}

// 👉 Reset data
const resetData = () => {
  // Close dialog - this will unmount all tab components due to v-if
  isDialogVisible.value = false
  
  // 👉 Reset data after dialog is closed
  nextTick(() => {
    currencyData.value = null
    formData.value = {
      currency: '',
      currency_symbol: '',
      exchange_rate: '',
      status: 'enable',
    }
    formValidated.value = false
    formRef.value?.resetValidation()
  })
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
                {{ dialogMode === 'Create' ? 'Add New Currency' : 'Edit Currency' }}
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
            <!-- 👉 Currency -->
            <VCol cols="12">
                <VTextField
                v-model="formData.currency"
                label="Name"
                hide-details
                placeholder="Enter Currency Name"
                density="compact"
                :rules="[requiredValidator]"
                class="required-field"
                />
            </VCol>
            <!-- 👉 Dollar Sign -->
            <VCol cols="12">
                <VTextField
                    v-model="formData.currency_symbol"
                    label="Currency Symbol"
                    hide-details
                    placeholder="Enter Currency Symbol"
                    density="compact"
                />
            </VCol>
            <!-- 👉 Exchange Rate -->
            <VCol cols="12">
                <VTextField
                    v-model="formData.exchange_rate"
                    label="Exchange Rate (Currency to HKD)"
                    type="number"
                    step="0.01"
                    placeholder="Enter Exchange Rate"
                    density="compact"
                    :rules="[requiredValidator, exchangeRateValidator]"
                    class="required-field"
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
