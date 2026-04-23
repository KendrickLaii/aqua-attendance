<script setup lang="ts">
import type { Content } from '@/types/client'
import type { BasicInformationData } from '@/types/working-section'

const formData = defineModel<BasicInformationData>('formData', { required: true })

const props = withDefaults(
  defineProps<{
    clientData: Content
    clientProfileRaw?: Record<string, any> | null
  }>(),
  { clientProfileRaw: null },
)

// Show all API result fields; label: snake_case -> Title Case
function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/(?:^|\s)\S/g, c => c.toUpperCase())
}
/** Given year end date (d-m-Y), return year start: (end - 1 year) + 1 day. Handles leap years and month lengths. */
function computeYearStartFromEnd(yearEndStr: string): string {
  const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(yearEndStr)
  if (!match) return ''
  const d = new Date(`${match[3]}-${match[2]}-${match[1]}T12:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  d.setFullYear(d.getFullYear() - 1)
  d.setDate(d.getDate() + 1)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${day}-${m}-${y}`
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
  if (formData.value[endKey] === value) return
  formData.value[endKey] = value
  if (!formData.value[startKey]?.trim()) {
    const start = computeYearStartFromEnd(value)
    if (start) formData.value[startKey] = start
  }
}

function normalizeDateInput(raw: string): string {
  const trimmed = String(raw || '').trim()
  if (!trimmed) return ''

  const match = /^(\d{1,2})-(\d{1,2})-(\d{4})$/.exec(trimmed)
  if (!match) return ''

  const day = Number(match[1])
  const month = Number(match[2])
  const year = Number(match[3])
  const dateObj = new Date(year, month - 1, day)
  const isValid = dateObj.getFullYear() === year
    && dateObj.getMonth() === month - 1
    && dateObj.getDate() === day

  if (!isValid) return ''
  return `${String(day).padStart(2, '0')}-${String(month).padStart(2, '0')}-${year}`
}

function normalizeDateField(
  key: 'f_year_start' | 'L_year_start' | 'engage_date' | 'due_date' | 'report_date',
) {
  formData.value[key] = normalizeDateInput(formData.value[key] || '')
}

function normalizeYearEndField(
  endKey: 'f_year_end' | 'L_year_end',
  startKey: 'f_year_start' | 'L_year_start',
) {
  const normalized = normalizeDateInput(formData.value[endKey] || '')
  formData.value[endKey] = normalized
  if (!normalized) return
  onYearEndChange(normalized, endKey, startKey)
}
const apiDisplayEntries = computed(() => {
  const raw = props.clientProfileRaw
  if (!raw || typeof raw !== 'object') return []
  return Object.entries(raw).map(([key, value]) => ({
    key,
    label: formatLabel(key),
    value: value === undefined || value === null || value === '' ? '-' : String(value),
  }))
})
const fiscalPeriodItems = [
  { title: 'Year/ Year', value: '0' },
  { title: 'Year/ Period', value: '1' },
  { title: 'Period/ Year', value: '2' },
  { title: 'Period/ Period', value: '3' },
]

const refForm = ref<{ validate: () => Promise<{ valid: boolean; errors: { id: string }[] }> } | null>(null)

async function validate() {
  const result = await refForm.value?.validate()
  const isValid = result?.valid ?? false
  if (isValid) return { valid: true, errors: [] as string[] }

  const errors = (result?.errors ?? []).map(({ id }) => {
    const label = document.querySelector<HTMLLabelElement>(`label[for="${id}"]:not([aria-hidden="true"])`)
    return label?.textContent?.trim() || id
  })
  return { valid: false, errors }
}

defineExpose({ validate })
</script>

<template>
  <VForm ref="refForm" @submit.prevent="">
    <VRow>
      <VCol cols="12" md="6">
        <VTextField
          v-model="formData.companyNameEn"
          density="compact"
          label="Company Name"
          readonly
          disabled
          placeholder="Enter company name"
          class="required-field"
          :rules="[requiredValidator]"
        />
        
      </VCol>
      <VCol cols="12" md="6">
        <VTextField
          v-model="formData.companyNumber"
          density="compact"
          label="Company Number"
          placeholder="Enter company number"
          readonly
          disabled
          class="required-field"
          :rules="[requiredValidator]"
        />
      </VCol>
      <VCol cols="12" md="6">
        <VTextField
          v-model="formData.title"
          density="compact"
          label="Title"
          placeholder="Enter title"
          hide-details
          class="required-field"
          :rules="[requiredValidator]"
        />
      </VCol>
      <VCol cols="12" md="6">
        <VTextField
          v-model="formData.referor"
          density="compact"
          label="Referor"
          placeholder="Enter referor"
        />
      </VCol>
      <VCol cols="12" md="6">
        <VTextField
          v-model="formData.year"
          density="compact"
          label="Year"
          :rules="[requiredValidator]"
          required
          readonly
          disabled
          placeholder="Enter year"
        />
      </VCol>
      <VCol cols="12" md="6">
        <VTextField
          v-model="formData.taxFileNumber"
          density="compact"
          label="Tax File Number"
          placeholder="Enter tax file number"
          required
          hide-details
          class="required-field"
        />
      </VCol>
      <VCol cols="12" md="6">
        <div class="d-flex flex-column">
          <div class="w-100 d-flex gap-2 align-center mb-4">
            <div class="w-50 mb-2 required-field">
              <AppDateTimePicker
                :model-value="formData.f_year_end"
                name="f_year_end"
                label="Year end date"
                placeholder="Select year end date"
                density="compact"
                hide-details
                clearable
                :config="{ dateFormat: 'd-m-Y', allowInput: true }"
                :rules="[requiredValidator]"
                @update:model-value="(v: string) => onYearEndChange(v, 'f_year_end', 'f_year_start')"
                @blur="normalizeYearEndField('f_year_end', 'f_year_start')"
              />
            </div>
            <div class="w-50 mb-2 required-field">
              <AppDateTimePicker
                :model-value="formData.L_year_end"
                name="L_year_end"
                label="Prior year end date"
                placeholder="Select prior year end date"
                density="compact"
                hide-details
                clearable
                :config="{ dateFormat: 'd-m-Y', allowInput: true }"
                :rules="[requiredValidator]"
                @update:model-value="(v: string) => onYearEndChange(v, 'L_year_end', 'L_year_start')"
                @blur="normalizeYearEndField('L_year_end', 'L_year_start')"
              />
            </div>
          </div>
          <div class="w-100 d-flex gap-2">
            <div class="w-50 required-field">
              <AppDateTimePicker
                v-model="formData.f_year_start"
                name="f_year_start"
                label="Year start date"
                placeholder="Select year start date"
                density="compact"
                hide-details
                clearable
                :config="{ dateFormat: 'd-m-Y', allowInput: true }"
                :rules="[requiredValidator]"
                @blur="normalizeDateField('f_year_start')"
              />
            </div>
            <div class="w-50 required-field">
              <AppDateTimePicker
                v-model="formData.L_year_start"
                name="L_year_start"
                label="Prior year start date"
                placeholder="Select prior year start date"
                density="compact"
                hide-details
                clearable
                :config="{ dateFormat: 'd-m-Y', allowInput: true }"
                :rules="[requiredValidator]"
                @blur="normalizeDateField('L_year_start')"
              />
            </div>
          </div>
        </div>
      </VCol>
      <VCol cols="12" md="6">
        <div class="d-flex flex-column">
          <div class="w-100 d-flex gap-2 align-center mb-4">
            <div class="w-50 mb-2">
              <VTextField
                v-model="formData.year_of_assessment_ly"
                name="year_of_assessment_ly"
                label="Year of assessment (LY)"
                density="compact"
                hide-details
                disabled
                class="required-field"
                :rules="[requiredValidator]"
              />
            </div>
            <span class="text-body-1 font-weight-medium text-high-emphasis mb-2">/</span>
            <div class="w-50 mb-2">
              <VTextField
                :model-value="formData.year_of_assessment"
                name="year_of_assessment"
                label="Year of assessment"
                :placeholder="`e.g. ${new Date().getFullYear()}`"
                density="compact"
                hide-details
                maxlength="4"
                @update:model-value="onYearOfAssessmentChange"
                class="required-field"
                :rules="[requiredValidator]"
              />
            </div>
          </div>
          <div class="w-100 d-flex gap-2 align-center">
            <div class="w-50">
              <VTextField
                v-model="formData.provisional_ly"
                name="provisional_ly"
                label="Provisional (LY)"
                density="compact"
                hide-details
                disabled
                class="required-field"
                :rules="[requiredValidator]"
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
                disabled
                class="required-field"
                :rules="[requiredValidator]"
              />
            </div>
          </div>
        </div>
      </VCol>
      <VCol cols="12" md="6">
        <VSelect
          v-model="formData.fiscal_period"
          name="fiscal_period"
          label="Fiscal period"
          placeholder="Select Fiscal period"
          density="compact"
          hide-details
          :items="fiscalPeriodItems"
          class="required-field"
          :rules="[requiredValidator]"
        />
      </VCol>
      <VCol md="6" class="d-none d-md-block" />
      <VCol cols="12" md="6">
        <div class="d-flex flex-column gap-4">
          <AppDateTimePicker
            v-model="formData.engage_date"
            name="engage_date"
            label="Engage date"
            placeholder="Select"
            density="compact"
            hide-details
            :config="{ dateFormat: 'd-m-Y', allowInput: true }"
            @blur="normalizeDateField('engage_date')"
          />
          <AppDateTimePicker
            v-model="formData.due_date"
            name="due_date"
            label="Due date"
            placeholder="Select"
            density="compact"
            hide-details
            :config="{ dateFormat: 'd-m-Y', allowInput: true }"
            @blur="normalizeDateField('due_date')"
          />
          <AppDateTimePicker
            v-model="formData.report_date"
            name="report_date"
            label="Report date"
            placeholder="Select"
            density="compact"
            hide-details
            :config="{ dateFormat: 'd-m-Y', allowInput: true }"
            @blur="normalizeDateField('report_date')"
          />
        </div>
      </VCol>
      <VCol cols="12" md="6">
        <div class="d-flex flex-column gap-4">
          <VTextField
            v-model="formData.signing_partner"
            name="signing_partner"
            label="Signing partner"
            placeholder="Enter Signing partner"
            density="compact"
            hide-details
          />
          <VTextField
            v-model="formData.position_of_signing_partner"
            name="position_of_signing_partner"
            label="Position of signing partner"
            placeholder="e.g. Director"
            density="compact"
            hide-details
          />
          <VTextField
            v-model="formData.practising_certificate_number"
            name="practising_certificate_number"
            label="Practising certificate number"
            placeholder="Enter Practising certificate number"
            density="compact"
            hide-details
          />
        </div>
      </VCol>
      <VCol cols="12" md="6">
        <VTextarea
          v-model="formData.description"
          density="compact"
          label="Description"
          placeholder="Enter description"
          no-resize
        />
      </VCol>
      <VCol cols="12" md="6">
        <VTextarea
          v-model="formData.remark"
          density="compact"
          label="Remark"
          placeholder="Enter remark"
          no-resize
        />
      </VCol>
    </VRow>
  </VForm>

  <VCardText>
    <p class="text-subtitle-2 text-medium-emphasis mb-3">Search Result</p>
    <div class="search-result-scroll overflow-x-hidden">
      <VRow>
        <VCol
          v-for="entry in apiDisplayEntries"
          :key="entry.key"
          cols="6"
          md="3"
        >
          <p class="text-caption text-medium-emphasis mb-1">{{ entry.label }}</p>
          <p class="text-body-1 font-weight-medium">{{ entry.value }}</p>
        </VCol>
      </VRow>
    </div>
  </VCardText>
</template>

<style lang="scss" scoped>
.search-result-scroll {
  max-height: clamp(12rem, 40vh, 28rem);
  overflow-y: auto;
}
.required-field :deep(.v-field__field label::before),
.required-field :deep(.v-label::before) {
  content: "*";
  color: rgb(var(--v-theme-error));
  margin-left: 1px;
}
</style>
