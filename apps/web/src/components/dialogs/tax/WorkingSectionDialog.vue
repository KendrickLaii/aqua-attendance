<script setup lang="ts">
import type { WorkingSectionProperties } from '@/types/working-section'
import type { VForm } from 'vuetify/components/VForm'
import type { Content } from '@/types/client'
import { fuzzySearchClient } from '@/api/client'

// 👉 Form data interface
export interface FormData {
    companySearchQuery: string
    year: string
    uuid?: string
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
const workingSectionData = ref<WorkingSectionProperties | null>(null)
const formRef = ref<VForm>()
const formValidated = ref(false)
const currentYear = ref('')
// 👉 Form initial data
const formData = ref<FormData>({
    companySearchQuery: '',
    year: String(currentYear.value),
})
const isDatePickerOpen = ref(false)
const isSearching = ref(false)
const hasSearched = ref(false)
const onYearSelect = (year: number) => {
    formData.value.year = String(year)
    isDatePickerOpen.value = false
  }
// 👉 Method to open dialog - exposed to parent component
const openDialog = async (mode: 'Create' | 'Edit', data: WorkingSectionProperties | null = null) => {
  dialogMode.value = mode
  workingSectionData.value = data
  
  formData.value = {
    companySearchQuery: '',
      year: String(currentYear.value),
    }
  companySearchResults.value = []
  selectedCompany.value = null
  hasSearched.value = false
  formValidated.value = false
  formRef.value?.resetValidation()
  
  // Open dialog - components will mount due to v-if
  isDialogVisible.value = true
}

const companySearchResults = ref<Content[]>([])
const handleFuzzySearch = async () => {
  const keyword = formData.value.companySearchQuery.trim()
  if (!keyword) return

  isSearching.value = true
  hasSearched.value = true
  selectedCompany.value = null
  companySearchResults.value = []

  try {
    const res = await fuzzySearchClient(keyword)
    companySearchResults.value = res?.data?.content ?? []
  } catch {
    companySearchResults.value = []
  } finally {
    isSearching.value = false
  }
}
// 👉 Form submission: validate then emit create/edit with year and selected company uuid.
const handleSubmit = async () => {
  formValidated.value = true
  const validation = await formRef.value?.validate()
  const isValid = validation?.valid ?? false

  if (!isValid) {
    emit('showAlert', 'Please fill in all required fields')
    return
  }

  if (!selectedCompany.value) {
    emit('showAlert', 'Please select a company to create working section')
    return
  }

  const payload: FormData = {
    companySearchQuery: formData.value.companySearchQuery,
    year: formData.value.year.trim(),
    uuid: selectedCompany.value.uuid,
  }

  if (dialogMode.value === 'Create') {
    emit('create', payload)
  } else if (workingSectionData.value) {
    emit('edit', payload as FormData & { id: number })
  }
}
const selectedCompany = ref<Content | null>(null)

const selectCompany = ( company: Content ) =>{
  selectedCompany.value = company
  // console.log('selectCompany',selectedCompany.value)
}
// 👉 Reset data
const resetData = () => {
  // Close dialog - this will unmount all tab components due to v-if
  isDialogVisible.value = false
  
  // 👉 Reset data after dialog is closed
  nextTick(() => {
    workingSectionData.value = null
    formData.value = {
      companySearchQuery: '',
      year: String(currentYear.value),
    }
    companySearchResults.value = []
    selectedCompany.value = null
    hasSearched.value = false
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
    max-width="500px"
    scrollable
    v-model="isDialogVisible"
  >
    <VCard class="pa-sm-6 pa-4">
        <div class="d-flex justify-space-between align-center mb-4">
            <h5 class="text-h5">
                {{ dialogMode === 'Create' ? 'Create Working Section' : 'Edit Working Section' }}
            </h5>
            <!-- 👉 dialog close btn -->
            <DialogCloseBtn
                variant="text"
                size="default"
                @click="resetData"
            />
        </div>

        <VDivider />
        
        <VCardText class="pt-6">
        <VForm ref="formRef" @submit.prevent="">
          <VRow>
            <VCol cols="612">
          <VTextField 
            v-model="formData.year"
            label="Year"
            density="compact"
            hide-details
            :rules="[requiredValidator]"
            class="required-field"
          />
          </VCol>
          <VCol cols="12">
          <VTextField
            v-model="formData.companySearchQuery"
            label="Company name/ Company number"
            placeholder="Type company name or company number..."
            prepend-inner-icon="ri-search-line"
            density="compact"
            clearable
          />
          </VCol>
          <VCol cols="12">
          <VBtn
            variant="elevated"
            color="primary"
            :loading="isSearching"
            :disabled="isSearching"
            @click.prevent="handleFuzzySearch"
          >
            Search
          </VBtn>
        </VCol>
        </VRow>

        <!-- Results -->
        <div class="mt-4" style="block-size: 300px; overflow-y: auto;">
          <VProgressCircular v-if="isSearching" indeterminate class="d-block mx-auto my-4" />

          <template v-else-if="companySearchResults.length">
            <VList density="compact">
              <VListItem
                v-for="company in companySearchResults"
                :key="company.company_no"
                class="cursor-pointer"
                :class="{ 'selected-company': selectedCompany === company }"
                @click="selectCompany(company)"
              >
                <VListItemTitle>{{ company.company_name_en }}</VListItemTitle>
                <VListItemSubtitle>{{ company.company_name }}</VListItemSubtitle>
                <VListItemSubtitle>{{ company.company_no }}</VListItemSubtitle>
              </VListItem>
            </VList>
          </template>

          <div v-else-if="hasSearched" class="text-center text-medium-emphasis pa-4">
            No results found
          </div>

          <div v-else class="text-center text-medium-emphasis pa-4">
            Start typing to search for a company
          </div>
        </div>
        </VForm>
        </VCardText>
        <VDivider />
              <!-- Date picker (commented out): uncomment to restore year picker
              <VMenu v-model="isDatePickerOpen" :close-on-content-click="false">
                <template #activator="{ props }">
                  <VTextField v-bind="props" :model-value="formData.year" label="Year" readonly :rules="[requiredValidator]" required />
                </template>
                <VDatePicker
                  class="year-picker"
                  hide-header
                  view-mode="year"
                  @update:year="onYearSelect"
                />
              </VMenu>
              -->
        <VCardText>

        </VCardText>
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
                type="button"
                variant="elevated"
                color="primary"
                :loading="isSearching"
                :disabled="isSearching"
                @click.prevent="handleSubmit"
            >
                    Submit
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
.year-picker {
 :deep(.v-date-picker-controls){
    display: none;
 }
 :deep(.v-date-picker-years){
  margin-top: 1rem;
 }
}
.selected-company {
  background-color: rgba(var(--v-theme-primary), 0.12) !important;

  :deep(.v-list-item-title) {
    color: rgb(var(--v-theme-primary));
    font-weight: 600;
  }
}
</style>
