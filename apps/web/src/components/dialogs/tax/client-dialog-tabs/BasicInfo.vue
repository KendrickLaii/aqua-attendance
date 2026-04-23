<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import { getClientProfileFromAquaAudit } from '@/api/client'
import type { AquaAuditClientProfile } from '@/types/client'

interface BasicInfoFormData {
  L_year_end: string
  L_year_start: string
  business_nature_uuid: string
  company_name: string
  company_name_en: string
  company_no: string
  contact_person: string
  currency: string | null
  due_date: string
  engage_date: string
  f_year_end: string
  f_year_start: string
  fiscal_period: string | null
  incorporation_date: string
  main_signer: string
  manager: string
  place_of_incorporation: string
  position_of_signing_partner: string
  practising_certificate_number: string
  principal_activity: string
  provisional: string
  provisional_ly: string
  registered_office: string
  report_date: string
  reportin_standards: string
  signing_partner: string
  staff_in_charge: string
  status: string
  tax_file_no: string
  tax_file_no_part1: string
  tax_file_no_part2: string
  year_of_assessment: string
  year_of_assessment_ly: string
  main_signer_position: string | null
}

interface Props {
  initialData?: Partial<BasicInfoFormData>
  currencyItems?: Array<{ label: string; value: string }>
}

interface Emit {
  (e: 'update:data', value: Partial<BasicInfoFormData>): void
  (e: 'showAlert', payload: { message: string; type?: 'success' | 'error' }): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emit>()

const refForm = ref<VForm>()
const isFormValid = ref(false)

// Default form data
const defaultFormData: BasicInfoFormData = {
  L_year_end: '',
  L_year_start: '',
  business_nature_uuid: '',
  company_name: '',
  company_name_en: '',
  company_no: '',
  contact_person: '',
  currency: null,
  due_date: '',
  engage_date: '',
  f_year_end: '',
  f_year_start: '',
  fiscal_period: null,
  incorporation_date: '',
  main_signer: '',
  manager: '',
  place_of_incorporation: '',
  position_of_signing_partner: '',
  practising_certificate_number: '',
  principal_activity: '',
  provisional: '',
  provisional_ly: '',
  registered_office: '',
  report_date: '',
  reportin_standards: 'SME-FRS',
  signing_partner: '',
  staff_in_charge: '',
  status: 'enable',
  tax_file_no: '',
  tax_file_no_part1: '',
  tax_file_no_part2: '',
  year_of_assessment: '',
  year_of_assessment_ly: '',
  main_signer_position: null,
}

// Form data
const formData = ref<BasicInfoFormData>({ ...defaultFormData })

/** Given year end date (Y-m-d), return year start: (end - 1 year) + 1 day. Handles leap years and month lengths. */
function computeYearStartFromEnd(yearEndStr: string): string {
  if (!yearEndStr || !/^\d{4}-\d{2}-\d{2}$/.test(yearEndStr)) return ''
  const d = new Date(yearEndStr + 'T12:00:00')
  if (Number.isNaN(d.getTime())) return ''
  d.setFullYear(d.getFullYear() - 1)
  d.setDate(d.getDate() + 1)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Restrict to max 4-digit integer (0–9999) and sync year_of_assessment_ly, provisional_ly, provisional. */
function onYearOfAssessmentChange(raw: string) {
  const digitsOnly = raw.replace(/\D/g, '').slice(0, 4)
  const num = digitsOnly === '' ? NaN : Math.min(parseInt(digitsOnly, 10), 9999)
  const sanitized = digitsOnly === '' ? '' : String(num)
  formData.value.year_of_assessment = sanitized
  if (sanitized === '' || Number.isNaN(num)) {
    formData.value.year_of_assessment_ly = ''
    formData.value.provisional_ly = ''
    formData.value.provisional = ''
  }
  else {
    formData.value.year_of_assessment_ly = String(num - 1)
    formData.value.provisional_ly = String(num)
    formData.value.provisional = String(num + 1)
  }
}

/** On year-end date change: update end field and, if start is empty, auto-fill start as (end - 1 year) + 1 day. */
function onYearEndChange(
  value: string,
  endKey: 'f_year_end' | 'L_year_end',
  startKey: 'f_year_start' | 'L_year_start',
) {
  formData.value[endKey] = value
  if (!formData.value[startKey]?.trim()) {
    const start = computeYearStartFromEnd(value)
    if (start) formData.value[startKey] = start
  }
}

// Flag to prevent circular updates during initialization
const isInitializing = ref(false)

// Watch for initial data changes
watch(() => props.initialData, (newData) => {
  isInitializing.value = true
  
  if (newData) {
    const d = newData as Partial<BasicInfoFormData>
    const taxFileNo = d.tax_file_no ?? ''
    const [taxFileNoPart1 = '', taxFileNoPart2 = ''] = taxFileNo.split('/')
    formData.value = {
      L_year_end: d.L_year_end ?? '',
      L_year_start: d.L_year_start ?? '',
      business_nature_uuid: d.business_nature_uuid ?? '',
      company_name: d.company_name ?? '',
      company_name_en: d.company_name_en ?? '',
      company_no: d.company_no ?? '',
      contact_person: d.contact_person ?? '',
      currency: d.currency ?? null,
      due_date: d.due_date ?? '',
      engage_date: d.engage_date ?? '',
      f_year_end: d.f_year_end ?? '',
      f_year_start: d.f_year_start ?? '',
      fiscal_period: d.fiscal_period ?? null,
      incorporation_date: d.incorporation_date ?? '',
      main_signer: d.main_signer ?? '',
      manager: d.manager ?? '',
      place_of_incorporation: d.place_of_incorporation ?? '',
      position_of_signing_partner: d.position_of_signing_partner ?? '',
      practising_certificate_number: d.practising_certificate_number ?? '',
      principal_activity: d.principal_activity ?? '',
      provisional: d.provisional ?? '',
      provisional_ly: d.provisional_ly ?? '',
      registered_office: d.registered_office ?? '',
      report_date: d.report_date ?? '',
      reportin_standards: d.reportin_standards ?? 'SME-FRS',
      signing_partner: d.signing_partner ?? '',
      staff_in_charge: d.staff_in_charge ?? '',
      status: d.status ?? 'enable',
      tax_file_no: taxFileNo,
      tax_file_no_part1: taxFileNoPart1.trim(),
      tax_file_no_part2: taxFileNoPart2.trim(),
      year_of_assessment: d.year_of_assessment ?? '',
      year_of_assessment_ly: d.year_of_assessment_ly ?? '',
      main_signer_position: d.main_signer_position ?? null,
    }
  } else {
    formData.value = { ...defaultFormData }
  }
  
  nextTick(() => {
    isInitializing.value = false
  })
}, { immediate: true })

// Watch formData and emit updates (but not during initialization). Combine tax_file_no from part1/part2 for API.
watch(formData, (newData) => {
  if (!isInitializing.value) {
    emit('update:data', {
      ...newData,
      tax_file_no: `${newData.tax_file_no_part1}/${newData.tax_file_no_part2}`,
    })
  }
}, { deep: true })

// Validation method
const validate = async () => {
  const validation = await refForm.value?.validate()
  const isValid = validation?.valid || false

  if (!isValid) {
    // old method, hardcoded label
    // const errors: string[] = []
    // if (!formData.value.company_name_en) errors.push('Company Name (EN)')

    // Dynamically resolve field labels from DOM using the id Vuetify assigns to each failed input.
    // aria-hidden="true" labels are the floating duplicates — exclude them to get the real label text.
    const errors = (validation?.errors ?? []).map(({ id }) => {
      const labelEl = document.querySelector<HTMLLabelElement>(
        `label[for="${id}"]:not([aria-hidden="true"])`,
      )
      return labelEl?.textContent?.trim() || String(id)
    })
    return { valid: false, errors }
  }

  return { valid: true }
}

// Reset method
const reset = () => {
  formData.value = { ...defaultFormData }
  refForm.value?.reset()
}

const pickNonEmpty = (incoming: string, current: string) => incoming?.trim() ? incoming : current

const convertYmdToDmy = (dateStr: string) => {
  if (!dateStr?.trim()) return ''
  const match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return dateStr

  const [, year, month, day] = match
  return `${day}-${month}-${year}`
}

const applyAquaAuditProfileToForm = (profile: AquaAuditClientProfile) => {
  const [taxFileNoPart1 = '', taxFileNoPart2 = ''] = (profile.tax_file_no || '').split('/')

  formData.value = {
    ...formData.value,
    company_no: pickNonEmpty(profile.company_no, formData.value.company_no),
    company_name: pickNonEmpty(profile.company_name, formData.value.company_name),
    company_name_en: pickNonEmpty(profile.company_name_en, formData.value.company_name_en),
    contact_person: pickNonEmpty(profile.contact_person, formData.value.contact_person),
    principal_activity: pickNonEmpty(profile.principal_activity, formData.value.principal_activity),
    place_of_incorporation: pickNonEmpty(profile.place_of_incorporation, formData.value.place_of_incorporation),
    registered_office: pickNonEmpty(profile.registered_office, formData.value.registered_office),
    engage_date: pickNonEmpty(profile.engage_date, formData.value.engage_date),
    report_date: pickNonEmpty(profile.report_date, formData.value.report_date),
    incorporation_date: pickNonEmpty(convertYmdToDmy(profile.incorporation_date), formData.value.incorporation_date),
    main_signer: pickNonEmpty(profile.main_signer, formData.value.main_signer),
    tax_file_no: pickNonEmpty(profile.tax_file_no, formData.value.tax_file_no),
    tax_file_no_part1: pickNonEmpty(taxFileNoPart1, formData.value.tax_file_no_part1),
    tax_file_no_part2: pickNonEmpty(taxFileNoPart2, formData.value.tax_file_no_part2),
    // API returns currency_uuid; keep best-effort mapping to existing currency field.
    // currency: pickNonEmpty(profile.currency_uuid, formData.value.currency || '') || null,
    // business_nature_uuid: pickNonEmpty(profile.business_nature_uuid, formData.value.business_nature_uuid),
  }
}

const getDataFromAquaAudit = async () => {
  if (!formData.value.company_no?.trim()) {
    emit('showAlert', { message: 'Company number cannot be blank', type: 'error' })
    return
  }

  try {
    const res = await getClientProfileFromAquaAudit(formData.value.company_no)

    if (
      res
      && typeof res === 'object'
      && 'status_code' in res
      && Number((res as any).status_code) !== 200
    ) {
      emit('showAlert', { message: 'Failed to get client profile', type: 'error' })
      return
    }

    applyAquaAuditProfileToForm(res)
  } catch (error) {
    console.error('Failed to get client profile from AQUA Audit:', error)
    emit('showAlert', { message: 'Failed to get client profile', type: 'error' })
  }
}

// Expose methods
defineExpose({
  validate,
  reset
})

// Dropdown items
const currencyItems = computed(() => props.currencyItems ?? [])
const fiscalPeriodItems = [
  { title: 'Year/ Year', value: '0' },
  { title: 'Year/ Period', value: '1' },
  { title: 'Period/ Year', value: '2' },
  { title: 'Period/ Period', value: '3' },
]
const statusItems = [
  { title: 'Enable', value: 'enable' },
  { title: 'Disable', value: 'disable' },
]
const mainSignerPositionItems = ['Secretary', 'Manager', 'Director', 'Investment mangager','Provisional liquidator','Liquidator']
</script>

<template>
  <VForm ref="refForm" v-model="isFormValid" @submit.prevent="() => {}">
    <div class="mt-2">
      <VRow>
        <VCol cols="6">
          <span class="text-body-1 font-weight-medium text-high-emphasis">Company information</span>
          <VTextField
            v-model="formData.company_name_en"
            name="company_name_en"
            label="Company Name (EN)"
            placeholder="Enter Company Name (EN)"
            density="compact"
            hide-details
            class="my-2 required-field"
            :rules="[requiredValidator]"
          />
          <VTextField
            v-model="formData.company_name"
            name="company_name"
            label="Company Name (CN)"
            placeholder="Enter Company Name (CN)"
            density="compact"
            class="mb-2"
          />
          <VTextField
            v-model="formData.company_no"
            name="company_no"
            label="Company no."
            placeholder="Enter Company no."
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />
          <VBtn
          color="primary"
          variant="elevated"
          size="x-small"
          @click="getDataFromAquaAudit"
          style="margin-bottom: 10px;"
        >
          Get from AQUA Audit
        </VBtn>
          <div class="mb-2 required-field">
            <AppDateTimePicker
              v-model="formData.incorporation_date"
              name="incorporation_date"
              label="Incorporation date"
              placeholder="Select Incorporation date"
              density="compact"
              hide-details
              :rules="[requiredValidator]"
              :config="{ dateFormat: 'd-m-Y' }"
            />
          </div>
          <div class="d-flex gap-2 mb-2 align-center">
            <VTextField
              v-model="formData.tax_file_no_part1"
              name="tax_file_no_part1"
              label="Tax file no."
              placeholder="e.g. 22"
              density="compact"
              hide-details
              class="w-25 required-field"
              :rules="[requiredValidator]"
            />
            <span class="text-body-1 font-weight-medium text-high-emphasis">/</span>
            <VTextField
              v-model="formData.tax_file_no_part2"
              name="tax_file_no_part2"
              label="Tax file no."
              placeholder="e.g. 23456789"
              density="compact"
              hide-details
              class="w-75 required-field"
              :rules="[requiredValidator]"
            />
          </div>
          <VSelect
            v-model="formData.currency"
            name="currency"
            :items="currencyItems"
            item-title="label"
            item-value="value"
            label="Currency"
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />
          <VTextField
            v-model="formData.place_of_incorporation"
            name="place_of_incorporation"
            label="Place of incorporation"
            placeholder="Enter Place of incorporation"
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />
          <VTextField
            v-model="formData.business_nature_uuid"
            name="business_nature_uuid"
            label="Business nature"
            placeholder="Enter Business nature"
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />
          <VTextField
            v-model="formData.principal_activity"
            name="principal_activity"
            label="Principal activity"
            placeholder="Enter Principal activity"
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />
          <VTextField
            v-model="formData.main_signer"
            name="main_signer"
            label="Main signer"
            placeholder="Enter Main signer"
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />
          <VSelect
            v-model="formData.main_signer_position"
            name="main_signer_position"
            label="Main signer position"
            placeholder="Select Main signer position"
            density="compact"
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
            :items="mainSignerPositionItems"
          />
          <VTextarea
            v-model="formData.registered_office"
            name="registered_office"
            label="Registered office"
            placeholder="Enter Registered office"
            density="compact"
            rows="3"
            no-resize
            hide-details
            class="mb-2 required-field"
            :rules="[requiredValidator]"
          />

          <!-- <span class="text-body-1 font-weight-medium text-high-emphasis">Fiscal & assessment years</span>
          <div class="d-flex flex-column">
            <div class="w-100 my-2 d-flex gap-2 align-center">
              <div class="w-50">
                <AppDateTimePicker
                  :model-value="formData.f_year_end"
                  name="f_year_end"
                  label="Year end date"
                  placeholder="Select year end date"
                  density="compact"
                  hide-details
                  clearable
                  :config="{ dateFormat: 'Y-m-d' }"
                  @update:model-value="(v: string) => onYearEndChange(v, 'f_year_end', 'f_year_start')"
                />
              </div>
              <div class="w-50">
                <AppDateTimePicker
                  :model-value="formData.L_year_end"
                  name="L_year_end"
                  label="Prior year end date"
                  placeholder="Select prior year end date"
                  density="compact"
                  hide-details
                  clearable
                  :config="{ dateFormat: 'Y-m-d' }"
                  @update:model-value="(v: string) => onYearEndChange(v, 'L_year_end', 'L_year_start')"
              />
              </div>
            </div>
            <div class="w-100 mb-2 d-flex gap-2">
              <div class="w-50">
                <AppDateTimePicker
                  v-model="formData.f_year_start"
                  name="f_year_start"
                  label="Year start date"
                  placeholder="Select year start date"
                  density="compact"
                  hide-details
                  clearable
                  :config="{ dateFormat: 'Y-m-d' }"
                />
              </div>
              <div class="w-50">
                <AppDateTimePicker
                  v-model="formData.L_year_start"
                  name="L_year_start"
                  label="Prior year start date"
                  placeholder="Select prior year start date"
                  density="compact"
                  hide-details
                  clearable
                  :config="{ dateFormat: 'Y-m-d' }"
                />
              </div>
            </div>
          </div>
          <VSelect
            v-model="formData.fiscal_period"
            name="fiscal_period"
            label="Fiscal period"
            placeholder="Select Fiscal period"
            density="compact"
            hide-details
            :items="fiscalPeriodItems"
            class="mb-2"
          />
          <VTextField
            v-model="formData.reportin_standards"
            name="reportin_standards"
            label="Reporting standards"
            placeholder="e.g. HKFRS"
            density="compact"
            hide-details
            class="mb-2"
          />
          <div class="d-flex flex-column">
            <div class="w-100 mb-2 d-flex gap-2 align-center">
              <div class="w-50">
                <VTextField
                  v-model="formData.year_of_assessment_ly"
                  name="year_of_assessment_ly"
                  label="Year of assessment (LY)"
                  density="compact"
                  hide-details
                  disabled
                />
              </div>
              <span class="text-body-1 font-weight-medium text-high-emphasis">/</span>
              <div class="w-50">
                <VTextField
                  :model-value="formData.year_of_assessment"
                  name="year_of_assessment"
                  label="Year of assessment"
                  :placeholder="`e.g. ${new Date().getFullYear()}`"
                  density="compact"
                  hide-details
                  maxlength="4"
                  @update:model-value="onYearOfAssessmentChange"
                />
              </div>
            </div>
            <div class="w-100 mb-2 d-flex gap-2 align-center">
              <div class="w-50">
                <VTextField
                  v-model="formData.provisional_ly"
                  name="provisional_ly"
                  label="Provisional (LY)"
                  density="compact"
                  hide-details
                  class="mb-2"
                  disabled
                />
              </div>
              <span class="text-body-1 font-weight-medium text-high-emphasis">/</span>
              <div class="w-50">
                <VTextField
                  v-model="formData.provisional"
                  name="provisional"
                  label="Provisional"
                  density="compact"
                  hide-details
                  class="mb-2"
                  disabled
                />
              </div>
            </div>
          </div> -->
        </VCol>
        <VCol cols="6">
          <span class="text-body-1 font-weight-medium text-high-emphasis">Contact & staff</span>
          <VTextField
            v-model="formData.contact_person"
            name="contact_person"
            label="Contact person"
            placeholder="Enter Contact person"
            density="compact"
            hide-details
            class="my-2"
          />
          <VTextField
            v-model="formData.staff_in_charge"
            name="staff_in_charge"
            label="Staff in charge"
            placeholder="Enter Staff in charge"
            density="compact"
            hide-details
            class="mb-2"
          />
          <VTextField
            v-model="formData.manager"
            name="manager"
            label="Manager"
            placeholder="Enter Manager"
            density="compact"
            hide-details
            class="mb-2"
          />
          <!-- <span class="text-body-1 font-weight-medium text-high-emphasis">Dates & reporting</span>
          <AppDateTimePicker
            v-model="formData.engage_date"
            name="engage_date"
            label="Engage date"
            placeholder="Select"
            density="compact"
            hide-details
            class="my-2"
            :config="{ dateFormat: 'Y-m-d' }"
          />
          <AppDateTimePicker
            v-model="formData.due_date"
            name="due_date"
            label="Due date"
            placeholder="Select"
            density="compact"
            hide-details
            class="mb-2"
            :config="{ dateFormat: 'Y-m-d' }"
          />
          <AppDateTimePicker
            v-model="formData.report_date"
            name="report_date"
            label="Report date"
            placeholder="Select"
            density="compact"
            hide-details
            class="mb-2"
            :config="{ dateFormat: 'Y-m-d' }"
          />
          <span class="text-body-1 font-weight-medium text-high-emphasis">Signing partner</span>
          <VTextField
            v-model="formData.signing_partner"
            name="signing_partner"
            label="Signing partner"
            placeholder="Enter Signing partner"
            density="compact"
            hide-details
            class="my-2"
          />
          <VTextField
            v-model="formData.position_of_signing_partner"
            name="position_of_signing_partner"
            label="Position of signing partner"
            placeholder="e.g. Director"
            density="compact"
            hide-details
            class="mb-2"
          />
          <VTextField
            v-model="formData.practising_certificate_number"
            name="practising_certificate_number"
            label="Practising certificate number"
            placeholder="Enter Practising certificate number"
            density="compact"
            hide-details
            class="mb-2"
          /> -->
          <VSelect
            v-model="formData.status"
            name="status"
            :items="statusItems"
            item-title="title"
            item-value="value"
            label="Status"
            density="compact"
            hide-details
            class="mb-2"
            placeholder="Select Status"
          />
        </VCol>
      </VRow>
    </div>
  </VForm>
</template>

<style scoped>
.required-field :deep(.v-field__field label::before),
.required-field :deep(.v-label::before) {
  content: "*";
  color: rgb(var(--v-theme-error));
  margin-left: 1px;
}
</style>
