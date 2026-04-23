<script setup lang="ts">
import type {
  ApiTemplate,
  TemplateField,
  TemplateFieldValue,
} from '@/types/tax-return-field-setup'
import { parseContentToFields } from '@/types/tax-return-field-setup'
import ConfirmDialog from '@/components/dialogs/tax/ConfirmDialog.vue'

const router = useRouter()
const formData = defineModel<ApiTemplate[]>('formData', { default: () => [] })
const emit = defineEmits<{
  (e: 'reimport'): void
}>()

const props = withDefaults(
  defineProps<{
    templates?: ApiTemplate[]
    title?: string
    description?: string
  }>(),
  {
    templates: () => [],
    title: 'Tax Return',
    description: 'Complete the following fields according to the tax return.',
  }
)

type TemplateFieldWithValue = TemplateField & { value?: TemplateFieldValue }

function buildFieldsForTemplate(template: ApiTemplate): TemplateFieldWithValue[] {
  return parseContentToFields(template.content).map(f => ({
    ...f,
    value: null,
  }))
}

// UI state: synced from formData or initialized from templates
const fieldsByTemplate = ref<TemplateFieldWithValue[][]>([])

function getFieldKey(tplIndex: number, fieldName: string, fieldIndex: number): string {
  return `${tplIndex}-${fieldName}-${fieldIndex}`
}

function getFieldValue(tplIndex: number, fieldIndex: number): TemplateFieldValue {
  const row = fieldsByTemplate.value[tplIndex] ?? []
  const field = row[fieldIndex]
  return field?.value ?? null
}

function setFieldValue(tplIndex: number, fieldIndex: number, value: TemplateFieldValue) {
  const row = fieldsByTemplate.value[tplIndex]
  if (!row) return

  const field = row[fieldIndex]
  if (!field) return

  field.value = value
  // sync back to v-model (ApiTemplate shape)
  formData.value = (props.templates ?? []).map((tpl, i) => ({
    ...tpl,
    content: {
      fields: (fieldsByTemplate.value[i] ?? []).map(f => ({ ...f })),
    },
  }))
}

//remove 0 before number e.g. 01234 -> 1234
function normalizeIntegerOnBlur(tplIndex: number, fieldIndex: number) {
  const currentValue = getFieldValue(tplIndex, fieldIndex)
  if (currentValue === null || currentValue === undefined || currentValue === '')
    return

  const raw = String(currentValue).trim()
  if (!/^-?\d+$/.test(raw))
    return

  const normalized = Number.parseInt(raw, 10)
  setFieldValue(tplIndex, fieldIndex, Number.isNaN(normalized) ? currentValue : normalized)
}

// when templates or formData change, sync fieldsByTemplate
watch(
  [() => props.templates, formData],
  ([templates]) => {
    const list = (templates ?? []) as ApiTemplate[]
    if (!list.length) {
      fieldsByTemplate.value = []
      return
    }
    // use formData if it matches templates length and has content.fields; else init from templates
    const hasValidFormData =
      formData.value.length === list.length &&
      formData.value.every(item => (item.content?.fields?.length ?? 0) > 0)
    if (hasValidFormData) {
      fieldsByTemplate.value = formData.value.map(item =>
        (item.content?.fields ?? []).map(f => ({ ...f, value: f.value ?? null }))
      )
    } else {
      fieldsByTemplate.value = list.map(tpl => buildFieldsForTemplate(tpl))
      formData.value = list.map((tpl, i) => ({
        ...tpl,
        content: {
          fields: (fieldsByTemplate.value[i] ?? []).map(f => ({ ...f })),
        },
      }))
    }
  },
  { immediate: true, deep: true }
)

const isText = (type: string) => (type ?? '').toLowerCase() === 'text'
const isInteger = (type: string) => (type ?? '').toLowerCase() === 'integer'
const isDate = (type: string) => (type ?? '').toLowerCase() === 'date'
const isRadio = (type: string) => (type ?? '').toLowerCase() === 'radio'

const navigateToCreateTaxReturnFieldSetup = () => {
  router.push({
    name: 'tax-context-tax-return-field-setup',
    query: { action: 'create' },
  })
}

const showLeaveForFieldSetupConfirm = ref(false)

function promptNavigateToCreateTaxReturnFieldSetup() {
  showLeaveForFieldSetupConfirm.value = true
}

function confirmLeaveToCreateTaxReturnFieldSetup() {
  navigateToCreateTaxReturnFieldSetup()
}

const reImportFields = () => {
  showReImportConfirm.value = true
}

const showReImportConfirm = ref(false)

const confirmReImportFields = () => {
  // Clear current data first, then let parent fetch latest templates.
  formData.value = []
  fieldsByTemplate.value = []
  showReImportConfirm.value = false
  emit('reimport')
}

const cancelReImportFields = () => {
  showReImportConfirm.value = false
}
</script>

<template>
  <div>
    <h6 class="text-h6">{{ title }}</h6>
    <p class="text-body-1 text-medium-emphasis mb-4">{{ description }}</p>

    <template v-if="!templates?.length">
      <p class="text-body-2 text-medium-emphasis mb-3">
        No tax return field setup found for this year.
      </p>
      <VBtn
        color="primary"
        variant="elevated"
        size="small"
        @click="promptNavigateToCreateTaxReturnFieldSetup"
      >
        <VIcon icon="ri-add-line" class="me-1" />
        Create Tax Return Field Setup
      </VBtn>
    </template>

    <VForm v-else ref="formRef" @submit.prevent="">
      <div
        v-for="(template, tplIndex) in templates"
        :key="template.uuid ?? template.id ?? tplIndex"
        class="mb-6"
      >
        <h6 v-if="template.title" class="text-subtitle-1 font-weight-medium mb-1">
          {{ template.title }}
        </h6>
        <p v-if="template.description" class="text-body-2 text-medium-emphasis mb-3">
          {{ template.description }}
        </p>
        <VBtn
          color="primary"
          size="x-small"
          @click.stop.prevent="reImportFields"
          class="mb-2"
        >
          Re-import fields
        </VBtn>
        <VDivider />
        <!-- Scroll on outer wrapper so scrollbar aligns with header; sticky keeps header frozen -->
        <div class="tai-field-list tai-field-scroll-wrap mt-2">
          <div class="tai-field-sticky-head">
            <div class="tai-field-row tai-field-header">
              <span class="tai-col-no tai-header-text">Tax Return No.</span>
              <span class="tai-col-field tai-header-text">Field</span>
              <span class="tai-col-control tai-header-text">Value</span>
              <span class="tai-col-ref tai-header-text">Tax return ref.</span>
              <span class="tai-col-action" />
            </div>
            <VDivider />
          </div>

          <div
            v-for="(field, fieldIndex) in (fieldsByTemplate[tplIndex] ?? [])"
            :key="getFieldKey(tplIndex, field.name, fieldIndex)"
            class="tai-field-row"
          >
            <!-- col 1: tax_return_number -->
              <span class="tai-col-no text-body-2 text-medium-emphasis">
                <VChip class="tai-col-no-chip" label>{{ field.tax_return_number || '-' }}</VChip>
              </span>

              <!-- col 2: label -->
              <span class="tai-col-field text-body-2">{{ field.name }}</span>

              <!-- col 3: value control -->
              <div class="tai-col-control">
                <!-- text -->
                <VTextField
                  v-if="isText(field.type ?? 'text')"
                  :model-value="String(getFieldValue(tplIndex, fieldIndex) ?? '')"
                  clearable
                  type="text"
                  density="compact"
                  hide-details
                  class="tai-value-right-input"
                  @update:model-value="(v: string | number) => setFieldValue(tplIndex, fieldIndex, v)"
                />
                <!-- integer -->
                <VTextField
                  v-else-if="isInteger(field.type ?? '')"
                  :model-value="getFieldValue(tplIndex, fieldIndex)"
                  type="number"
                  clearable
                  density="compact"
                  hide-details
                  class="no-number-spin tai-value-right-input"
                  @update:model-value="(v: string | number) => setFieldValue(tplIndex, fieldIndex, v)"
                  @blur="normalizeIntegerOnBlur(tplIndex, fieldIndex)"
                />
                <!-- date -->
                <div
                  v-else-if="isDate(field.type ?? '')"
                  class="tai-date-right-wrap"
                >
                  <AppDateTimePicker
                    clearable
                    :model-value="String(getFieldValue(tplIndex, fieldIndex) ?? '')"
                    placeholder="Select date"
                    :config="{ dateFormat: 'd-m-Y', allowInput: true }"
                    @update:model-value="(v: string) => setFieldValue(tplIndex, fieldIndex, v || null)"
                  />
                </div>
                <!-- radio -->
                <VHover v-else-if="isRadio(field.type ?? '')" v-slot="{ isHovering, props: hoverProps }">
                  <div v-bind="hoverProps" class="d-flex align-center gap-2">
                    <VRadioGroup
                      class="d-flex justify-end"
                      :model-value="getFieldValue(tplIndex, fieldIndex)"
                      density="compact"
                      hide-details
                      inline
                      @update:model-value="(v: string | number | boolean | null) => setFieldValue(tplIndex, fieldIndex, typeof v === 'boolean' ? v : null)"
                    >
                      <VRadio style="margin-right: 4px;" :value="true" label="Yes" />
                      <VRadio style="margin-right: 4px;" :value="false" label="No" />
                      <VBtn
                      icon="ri-close-line"
                      size="x-small"
                      variant="text"
                      style="margin-right: 16px;"
                      :disabled="getFieldValue(tplIndex, fieldIndex) === null"
                      @click="setFieldValue(tplIndex, fieldIndex, null)"
                    />
                    </VRadioGroup>
                    
                  </div>
                </VHover>
                <!-- default to text -->
                <VTextField
                  v-else
                  :model-value="String(getFieldValue(tplIndex, fieldIndex) ?? '')"
                  clearable
                  type="text"
                  density="compact"
                  hide-details
                  class="tai-value-right-input"
                  @update:model-value="(v: string | number) => setFieldValue(tplIndex, fieldIndex, v)"
                />
              </div>

              <!-- col 4: tax return reference -->
              <span class="tai-col-ref text-body-2 text-medium-emphasis">
                <VChip class="tai-col-no-chip" label>{{ field.tax_return_reference || '-' }}</VChip>
              </span>

              <!-- col 5: eye icon tooltip -->
              <div class="tai-col-action d-flex align-center justify-center">
                <VTooltip location="left" max-width="280">
                  <template #activator="{ props: tooltipProps }">
                    <VBtn v-bind="tooltipProps" icon size="x-small" variant="text">
                      <VIcon icon="ri-eye-line" size="16" />
                    </VBtn>
                  </template>
                  <div class="tai-tooltip-content">
                    <div class="tai-tooltip-row">
                      <span class="tai-tooltip-key">Aqua mapping:</span>
                      <span class="tai-tooltip-val">{{ field.aqua_mapping || '-' }}</span>
                    </div>
                    <div class="tai-tooltip-row">
                      <span class="tai-tooltip-key">IRD mapping:</span>
                      <span class="tai-tooltip-val">{{ field.ird_mapping || '-' }}</span>
                    </div>
                    <div class="tai-tooltip-row">
                      <span class="tai-tooltip-key">Tax return no.:</span>
                      <span class="tai-tooltip-val">{{ field.tax_return_number || '-' }}</span>
                    </div>
                    <div class="tai-tooltip-row">
                      <span class="tai-tooltip-key">Tax return ref.:</span>
                      <span class="tai-tooltip-val">{{ field.tax_return_reference || '-' }}</span>
                    </div>
                  </div>
                </VTooltip>
              </div>
            </div>
        </div>
      </div>
    </VForm>

    <ConfirmDialog
      v-model="showLeaveForFieldSetupConfirm"
      header="Leave this page?"
      text="This action will take you away from the current page.<br> Any unsaved changes on this page may be lost.<br> Do you want to continue?"
      confirm-button-text="Continue"
      confirm-button-color="error"
      max-width="500"
      use-html
      @confirm="confirmLeaveToCreateTaxReturnFieldSetup"
    />

    <ConfirmDialog
      v-model="showReImportConfirm"
      header="Confirm Re-import"
      text="Do you want to re-import fields? Existing data will be cleared."
      confirm-button-text="Re-import"
      confirm-button-color="error"
      max-width="500"
      @confirm="confirmReImportFields"
      @cancel="cancelReImportFields"
    />
  </div>
</template>

<style lang="scss" scoped>
.tai-field-list {
  display: flex;
  flex-direction: column;
}

/* Share the same vertical scrollbar with data rows, sticky header; scrollbar-gutter reduces layout shift when the scrollbar appears or disappears */
.tai-field-scroll-wrap {
  max-height: 45vh;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.tai-field-sticky-head {
  position: sticky;
  top: 0;
  z-index: 2;
  background: rgb(var(--v-theme-surface));
  padding-bottom: 0;
}

.tai-field-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding-block: 6px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));

  &:last-child {
    border-bottom: none;
  }

  &.tai-field-header {
    min-height: 32px;
    padding-block: 4px;
  }
}

.tai-header-text {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  letter-spacing: 0.02em;
}

// col 1: tax_return_number
.tai-col-no {
  flex: 0 0 80px;
  width: 80px;
  word-break: break-word;
  display: flex;
  text-align: center;
  align-items: center;
  justify-content: center;
}
.tai-col-no-chip{
  width: 65px;
  display:flex;
  justify-content: center;
  align-items: center;
}
// col 2: label (field name)
.tai-col-field {
  flex: 1 1 0;
  min-width: 0;
  word-break: break-word;
}

// col 3: value control
.tai-col-control {
  flex: 0 0 300px;
  width: 300px;
}

// col 4: tax return reference
.tai-col-ref {
  flex: 0 0 80px;
  width: 80px;
  min-width: 80px;
  word-break: break-word;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

// col 5: action
.tai-col-action {
  flex: 0 0 40px;
  width: 40px;
}

.tai-field-header .tai-col-action {
  display: flex;
  align-items: center;
  justify-content: center;
}

// eye tooltip
.tai-tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 2px 0;
  font-size: 0.75rem;
}

.tai-tooltip-row {
  display: flex;
  gap: 6px;
}

.tai-tooltip-key {
  flex: 0 0 auto;
  font-weight: 600;
  white-space: nowrap;
  opacity: 0.85;
}

.tai-tooltip-val {
  word-break: break-all;
}

.no-number-spin :deep(input[type='number']) {
  appearance: textfield;
  -moz-appearance: textfield;
}

.no-number-spin :deep(input[type='number']::-webkit-outer-spin-button),
.no-number-spin :deep(input[type='number']::-webkit-inner-spin-button) {
  -webkit-appearance: none;
  margin: 0;
}

.tai-value-right-input :deep(input) {
  text-align: right;
}

/* Keep clear icon hidden/collapsed by default, expand on hover/focus. */
.tai-value-right-input :deep(.v-field__clearable),
.tai-date-right-wrap :deep(.v-field__clearable) {
  width: 0;
  opacity: 0;
  margin-inline-start: 0;
  overflow: hidden;
  pointer-events: none;
  transition: width 0.15s ease, opacity 0.15s ease, margin-inline-start 0.15s ease;
}

.tai-value-right-input:hover :deep(.v-field__clearable),
.tai-value-right-input:focus-within :deep(.v-field__clearable),
.tai-date-right-wrap:hover :deep(.v-field__clearable),
.tai-date-right-wrap:focus-within :deep(.v-field__clearable)  {
  width: 22px;
  opacity: 1;
  margin-inline-start: 4px;
  pointer-events: auto;
}

.tai-date-right-wrap :deep(.v-field__input),
.tai-date-right-wrap :deep(.flat-picker-custom-style),
.tai-date-right-wrap :deep(.flatpickr-input),
.tai-date-right-wrap :deep(input.flatpickr-input) {
  text-align: right !important;
  padding-inline: var(--v-field-padding-start) var(--v-field-padding-end) !important;
}
</style>
