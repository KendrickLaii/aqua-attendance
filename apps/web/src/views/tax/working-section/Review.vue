<script setup lang="ts">
/**
 * Review.vue — Final review screen for a tax working section.
 *
 * ──────────────────────────────────────────────────────────────────
 * REFACTORING SUMMARY (what changed and why)
 * ──────────────────────────────────────────────────────────────────
 *
 * BEFORE: This file was ~600 lines of script containing formatting helpers,
 *   attachment CRUD, tax-computation mapping, clipboard-copy logic, and
 *   template type-guards — all in one flat list.
 *
 * AFTER: The logic is split into focused modules:
 *
 *   @/utils/review-format.ts
 *     Pure formatting functions (formatKeyLabel, formatPrimitive, formatAmount,
 *     toRoman, etc.) and the shared KeyValueRow type.
 *     → Independently testable, reusable by other views.
 *
 *   @/composables/useAttachments.ts
 *     All attachment state, API loading, base64 conversion, and OneDrive opener.
 *     → The composable owns its own reactive refs; Review.vue just binds them.
 *
 *   @/composables/useTaxComputationReview.ts
 *     Maps raw API data → structured schedules, pre-processes dataContentList
 *     for the "Profits Tax Computation" schedule, and flattens data for clipboard.
 *     → KEY FIX: The template used to call handleProfitsTaxComputationDataContent()
 *       TWICE per schedule (once in v-if, once in v-for). Now the composable
 *       pre-computes `processedSchedules` so the template has zero duplicate work.
 *     → KEY FIX: Duplicated row-filtering logic between display and clipboard-copy
 *       is now a single shared `filterSelectedTableRows()` function.
 *
 *   @/composables/useTaxClipboard.ts
 *     Builds the pipe-delimited company-info string and orchestrates the
 *     copy-to-clipboard flow.
 *     → FIX: Removed bare console.log calls; errors are gated properly.
 *     → FIX: Fixed the `fisaclPeriodString` typo (was "fisacl", now "fiscal").
 *
 * This file (Review.vue) is now just the ORCHESTRATOR:
 *   - Declares props
 *   - Wires up composables
 *   - Holds the two small pieces of local logic that don't warrant a composable:
 *       • extractTaxAdditionalFields (template-specific backward-compat parsing)
 *       • isTaxAdditionalField / isTaxAdditionalFieldList (template type guards)
 *   - Contains the <template> and <style>
 *
 * OTHER FIXES:
 *   - `isDebugMode` simplified from `=== 'dev' ? true : false` → `=== 'dev'`
 *   - All bare console.log statements removed (errors still logged with console.error)
 * ──────────────────────────────────────────────────────────────────
 */

import type { Content } from '@/types/client'
import type { BasicInformationData } from '@/types/working-section'
import type { ApiTemplate } from '@/types/tax-return-field-setup'
import { parseContentToFields } from '@/types/tax-return-field-setup'

// Shared formatting utilities (extracted from this file → now reusable & testable)
import {
  isObjectLike,
  isComplexValue,
  formatPrimitive,
  formatAmount,
  toRoman,
  buildRowsFromObject,
  entriesOf,
} from '@/utils/review-format'
import type { KeyValueRow } from '@/utils/review-format'

// Composables (each encapsulates one domain of logic)
import { useAttachments } from '@/composables/useAttachments'
import { useTaxComputationReview, isTableContent, isCheckboxContent } from '@/composables/useTaxComputationReview'
import { useTaxClipboard } from '@/composables/useTaxClipboard'

// ────────────────────────────────────────────
// Props
// ────────────────────────────────────────────

interface Props {
  basicInformationData: BasicInformationData
  clientData?: Content | null
  taxAdditionalInformationData: ApiTemplate[]
  taxComputationData?: unknown
  workingRecordUuid?: string
}

const props = defineProps<Props>()

// Simplified: the ternary `=== 'dev' ? true : false` was redundant — `===` already returns a boolean.
const isDebugMode = import.meta.env.VITE_ENV_MODE === 'dev'

// ────────────────────────────────────────────
// Section navigation
// ────────────────────────────────────────────

type ReviewSectionKey = 'basic' | 'taxComputation' | 'taxReturn' | 'attachments'

const sectionItems: { key: ReviewSectionKey; label: string }[] = [
  { key: 'basic', label: 'Basic information' },
  { key: 'taxComputation', label: 'Tax computation' },
  { key: 'taxReturn', label: 'Tax return' },
  { key: 'attachments', label: 'Attachments' },
]

const selectedSection = ref<ReviewSectionKey>('basic')

// ────────────────────────────────────────────
// Attachments (composable)
// ────────────────────────────────────────────
// All attachment state, API loading, base64 conversion, and OneDrive opener
// are now encapsulated in `useAttachments`. The composable auto-loads on mount
// and watches `workingRecordUuid` for changes.

const {
  attachmentData,
  attachmentList,
  isOneDriveButtonLoading,
  getAttachmentListForPayload,
  getAttachmentRecordUuid,
  openOneDrive,
} = useAttachments({
  workingRecordUuid: computed(() => props.workingRecordUuid),
  companyNameEn: computed(() => props.basicInformationData?.companyNameEn ?? ''),
  fiscalYearEnd: computed(() => props.basicInformationData?.f_year_end ?? ''),
})

// Expose the same methods as before so the parent component can call them.
defineExpose({
  getAttachmentListForPayload,
  getAttachmentRecordUuid,
})

// ────────────────────────────────────────────
// Basic information & client data rows
// ────────────────────────────────────────────

const basicInfoRows = computed<KeyValueRow[]>(
  () => buildRowsFromObject(props.basicInformationData as unknown as Record<string, unknown>),
)

const clientDataRows = computed<KeyValueRow[]>(() => {
  const cd = props.clientData
  if (!cd)
    return []

  return buildRowsFromObject(cd as unknown as Record<string, unknown>)
})

// ────────────────────────────────────────────
// Tax return rows
// ────────────────────────────────────────────

/**
 * Extract fields from a tax return template.
 *
 * This function handles multiple API response formats for backward compatibility:
 *   1. content.fields (the standard/current format)
 *   2. content as a JSON string (older API versions)
 *   3. template.fields (legacy fallback)
 */
function extractTaxAdditionalFields(tpl: ApiTemplate): unknown[] {
  const fromObjectContent = parseContentToFields(tpl.content)
  if (fromObjectContent.length)
    return fromObjectContent

  const rawTpl = tpl as unknown as Record<string, unknown>
  const rawContent = rawTpl.content

  // Backward compatibility: some API responses store content as JSON string.
  if (typeof rawContent === 'string') {
    try {
      const parsed = JSON.parse(rawContent) as unknown
      if (Array.isArray(parsed))
        return parsed
      if (isObjectLike(parsed) && Array.isArray((parsed as Record<string, unknown>).fields))
        return (parsed as Record<string, unknown>).fields as unknown[]
    }
    catch {
      // no-op, keep fallback behavior
    }
  }

  if (Array.isArray(rawTpl.fields))
    return rawTpl.fields

  return []
}

const taxReturnRows = computed<KeyValueRow[]>(() => {
  const list = props.taxAdditionalInformationData ?? []
  if (!list.length)
    return []

  return list.map((tpl, index) => ({
    key: tpl.uuid ?? String(tpl.id ?? index),
    label: tpl.title || `Template ${index + 1}`,
    value: extractTaxAdditionalFields(tpl),
  }))
})

/** Type guard: check if a value is a tax return field (has a `name` property). */
function isTaxReturnField(val: unknown): val is Record<string, unknown> {
  if (!isObjectLike(val))
    return false
  return 'name' in val
}

/** Type guard: check if a value is an array of tax return fields. */
function isTaxReturnFieldList(val: unknown): val is Record<string, unknown>[] {
  return Array.isArray(val) && val.every(item => isTaxReturnField(item))
}

// ────────────────────────────────────────────
// Tax computation (composable)
// ────────────────────────────────────────────
// `useTaxComputationReview` handles:
//   - Mapping raw API data → structured TaxComputationMapped
//   - Pre-computing processedSchedules (fixes the double-call bug in the template)
//   - Flattening data for clipboard copy
//
// `processedSchedules` is the KEY improvement:
//   Previously the template called `handleProfitsTaxComputationDataContent()` TWICE
//   per schedule (once in v-if, once in v-for). That function does non-trivial filtering.
//   Now the composable pre-computes everything, so the template just iterates — no waste.

const {
  taxComputationMapped,
  processedSchedules,
  flattenTaxComputationData,
} = useTaxComputationReview(computed(() => props.taxComputationData))

// ────────────────────────────────────────────
// Clipboard copy (composable)
// ────────────────────────────────────────────
// `useTaxClipboard` builds the pipe-delimited string and handles the copy flow.
// The `fisaclPeriodString` typo from the original code is fixed inside the composable.

const {
  copyClientInformationAndTaxComputation,
} = useTaxClipboard({
  basicInformationData: () => props.basicInformationData,
  clientData: () => props.clientData,
  flattenTaxComputationData,
})
//tax return review print start
function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function formatTaxReturnPrintValue(value: unknown, fieldType?: unknown): string {
  const raw = formatPrimitive(value)
  if (!raw)
    return '-'

  const normalizedType = String(formatPrimitive(fieldType) || '').toLowerCase()
  if (normalizedType === 'integer') {
    const numeric = Number(raw.replaceAll(',', ''))
    if (!Number.isNaN(numeric) && Number.isFinite(numeric))
      return Math.trunc(numeric).toLocaleString('en-US')
    return raw
  }

  const match = raw.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/)
  if (!match)
    return raw

  const day = Number(match[1])
  const month = Number(match[2])
  const year = Number(match[3])
  const dateObj = new Date(year, month - 1, day)

  const isValidDate = dateObj.getFullYear() === year
    && dateObj.getMonth() === month - 1
    && dateObj.getDate() === day
  if (!isValidDate)
    return raw

  const monthShort = dateObj.toLocaleString('en-US', { month: 'short' })
  return `${monthShort} ${day},${year}`
}

function renderPrintValueCell(item: { type: string; value: string }): string {
  const cellStyle = 'border:1px solid #ccc; padding:8px; width:200px; min-width:200px;'
  const normalizedType = item.type.toLowerCase()

  if (normalizedType === 'integer' || normalizedType === 'date')
    return `<td style="${cellStyle} text-align:right;">${escapeHtml(item.value)}</td>`

  // Default display keeps right alignment; only radio uses split cells.
  if (normalizedType !== 'radio')
    return `<td style="${cellStyle} text-align:right;">${escapeHtml(item.value)}</td>`

  const normalized = item.value.trim().toLowerCase()
  const isYes = normalized === 'yes' || normalized === 'true'
  const leftValue = isYes ? escapeHtml(item.value) : '&nbsp;'
  const rightValue = isYes ? '&nbsp;' : escapeHtml(item.value)

  return `
    <td style="${cellStyle} padding:0;">
      <div style="display:flex; width:100%;">
        <span style="flex:1; border-right:1px solid #ccc; padding:8px; text-align:center;">${leftValue}</span>
        <span style="flex:1; padding:8px; text-align:center;">${rightValue}</span>
      </div>
    </td>
  `
}

const printTaxReturnInformation = () => {
  if (typeof window === 'undefined')
    return

  const flattenedFields = taxReturnRows.value.flatMap(row => {
    if (!isTaxReturnFieldList(row.value))
      return []
    console.log ("row.value",row.value)
    return row.value.map(field => ({
      taxReturnNo: formatPrimitive(field.tax_return_number) || '-',
      field: formatPrimitive(field.name) || '-',
      value: formatTaxReturnPrintValue(field.value, field.type),
      type: formatPrimitive(field.type) || '-',
      taxReturnRef: formatPrimitive(field.tax_return_reference) || '-',
    }))
  })

  const printWindow = window.open('', '_blank', 'width=1200,height=800')
  if (!printWindow)
    return

  const printContainer = printWindow.document.createElement('div')
  const headerLine1 = `${formatPrimitive(props.basicInformationData.companyNameEn) || '-'} (${formatPrimitive(props.basicInformationData.companyNumber) || '-'})`
  const headerLine2 = `${formatPrimitive(props.basicInformationData.taxFileNumber) || '-'}`
  const headerLine3 = `${formatPrimitive(props.basicInformationData.year_of_assessment_ly) || '-'} / ${formatPrimitive(props.basicInformationData.year_of_assessment) || '-'}`
  const tableRows = flattenedFields.length
    ? flattenedFields.map(item => `
      <tr data-field-type="${escapeHtml(item.type)}">
        <td style="border:1px solid #ccc; padding:8px;">${escapeHtml(item.taxReturnNo)}</td>
        <td style="border:1px solid #ccc; padding:8px;">${escapeHtml(item.field)}</td>
        ${renderPrintValueCell(item)}
        <td style="border:1px solid #ccc; padding:8px;">${escapeHtml(item.taxReturnRef)}</td>
      </tr>
    `).join('')
    : `
      <tr>
        <td colspan="6" style="text-align:center; color:#666;">No data to display.</td>
      </tr>
    `

  printContainer.innerHTML = `
    <div style="zoom:0.8;">
    <h4 style="margin:0 0 8px;">
      <div>${escapeHtml(headerLine1)}</div>
      <div>${escapeHtml(headerLine2)}</div>
      <div>${escapeHtml(headerLine3)}</div>
    </h4>
    <table style="width:100%; border-collapse:collapse; font-family:Arial, sans-serif; font-size:12px;">
      <thead>
        <tr>
          <th style="border:1px solid #ccc; padding:8px; background:#f4f4f4;">Tax return No.</th>
          <th style="border:1px solid #ccc; padding:8px; background:#f4f4f4;">Field</th>
          <th style="border:1px solid #ccc; padding:8px; background:#f4f4f4; width:200px; min-width:200px;">Value</th>
          <th style="border:1px solid #ccc; padding:8px; background:#f4f4f4;">Tax return ref.</th>
        </tr>
      </thead>
      <tbody>
        ${tableRows}
      </tbody>
    </table>
    </div>
  `

  printWindow.document.body.innerHTML = ''
  printWindow.document.body.appendChild(printContainer)
  printWindow.document.title = `${props.basicInformationData.companyNameEn} - Tax Return ${formatPrimitive(props.basicInformationData.year_of_assessment_ly)} / ${formatPrimitive(props.basicInformationData.year_of_assessment)}`
  printWindow.document.close()
}
//tax return review print end
</script>

<template>
  <div class="review-layout">
    <aside class="review-nav">
      <div class="d-flex gap-1 align-center">
        <h6 class="text-h6">
          Review
        </h6>
          <VBtn 
            title="Copy client information and tax computation (Schedule 1)"
            color="primary"
            size="x-small"
            icon="ri-clipboard-line"
            @click.stop.prevent="copyClientInformationAndTaxComputation"
          />
      </div>
      <VList density="compact" nav>
        <VListItem
          v-for="item in sectionItems"
          :key="item.key"
          :value="item.key"
          :active="selectedSection === item.key"
          rounded="lg"
          @click="selectedSection = item.key"
        >
          <VListItemTitle>{{ item.label }}</VListItemTitle>
        </VListItem>
      </VList>
    </aside>

    <div class="review-main">
      <VCard class="review-card overflow-y-auto">
        <VCardText class="review-card-content">
          <template v-if="selectedSection === 'basic'">
            <VExpansionPanels multiple class="review-basic-expansion-panels">
              <VExpansionPanel>
                <VExpansionPanelTitle class="d-flex gap-1 align-center">
                  Basic information
                </VExpansionPanelTitle>
                <VExpansionPanelText>
                  <div v-if="!basicInfoRows.length" class="text-medium-emphasis">No data to display.</div>
                  <div v-else class="review-grid">
                    <template v-for="row in basicInfoRows" :key="row.key">
                      <div class="review-key">{{ row.label }}</div>
                      <div class="review-value">
                        <span v-if="!isComplexValue(row.value)">{{ formatPrimitive(row.value) }}</span>
                        <span v-else>{{ JSON.stringify(row.value, null, 2) }}</span>
                      </div>
                    </template>
                  </div>
                </VExpansionPanelText>
              </VExpansionPanel>

              <VExpansionPanel>
                <VExpansionPanelTitle class="d-flex gap-1 align-center">
                  Client information
                </VExpansionPanelTitle>
                <VExpansionPanelText>
                  <div v-if="!clientDataRows.length" class="text-medium-emphasis">No client data to display.</div>
                  <div v-else class="review-grid">
                    <template v-for="row in clientDataRows" :key="row.key">
                      <div class="review-key">{{ row.label }}</div>
                      <div class="review-value">
                        <span v-if="!isComplexValue(row.value)">{{ formatPrimitive(row.value) }}</span>
                        <span v-else>{{ JSON.stringify(row.value, null, 2) }}</span>
                      </div>
                    </template>
                  </div>
                </VExpansionPanelText>
              </VExpansionPanel>
            </VExpansionPanels>
          </template>

          <!--
            Tax Computation section
            ────────────────────────────────────────────
            KEY CHANGE: Previously the template called `handleProfitsTaxComputationDataContent()`
            TWICE per schedule (once in v-if to check complexity, once in v-for to iterate).
            That function does non-trivial filtering on every call.

            Now we use `processedSchedules` — a computed array from `useTaxComputationReview`
            where each schedule's `processedContent` is ALREADY filtered and normalised.
            The template simply iterates over it. Zero duplicate work.
          -->
          <template v-else-if="selectedSection === 'taxComputation'">
            <div class="d-flex gap-1 align-center">
              <h6 class="text-h6 mb-0">Tax computation</h6>
            </div>
            <VDivider class="my-2"/>
            <template v-if="!taxComputationMapped">
              <div class="text-medium-emphasis">No data to display.</div>
            </template>
            <template v-else>
              <div class="review-section">
                <!-- Tax rate (simple key-value) -->
                <div class="review-grid">
                  <div class="review-key">Tax Rate</div>
                  <div class="review-value">{{ taxComputationMapped.taxRate }}</div>
                </div>
                <!-- Tax schedules (expansion panels) -->
                <div class="review-row-stacked">
                <div class="review-key">Tax Schedules</div>
                <div class="review-row-stacked-content">
                  <VExpansionPanels multiple>
                    <!-- Uses processedSchedules instead of raw taxSchedules -->
                    <VExpansionPanel
                      v-for="(schedule, sIdx) in processedSchedules"
                      :key="sIdx"
                    >
                      <VExpansionPanelTitle>
                        {{ toRoman(schedule.scheduleNumber) }} {{ schedule.scheduleName }}
                      </VExpansionPanelTitle>
                      <VExpansionPanelText>
                        <!-- processedContent is already filtered — no function call needed here -->
                        <div
                          v-if="isComplexValue(schedule.processedContent)"
                          class="review-grid nested"
                        >
                          <template
                            v-for="sub in entriesOf(schedule.processedContent, 'Data content')"
                            :key="sub.key"
                          >
                            <div class="review-key">{{ sub.label }}</div>
                            <div class="review-value">
                              <!-- table content -->
                              <template v-if="isTableContent(sub.value)">
                                <VTable density="compact" class="review-data-table">
                                  <thead>
                                    <tr>
                                      <th class="review-col-name">Name</th>
                                      <th class="review-col-sch">Sch.</th>
                                      <th class="review-col-amount">Amount</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <tr v-for="(r, ri) in sub.value.rows" :key="ri">
                                      <td class="review-col-name">{{ r.name ?? '-' }}</td>
                                      <td class="review-col-sch">{{ r.schedule ?? '-' }}</td>
                                      <td class="review-col-amount">{{ formatAmount(r.amount) }}</td>
                                    </tr>
                                  </tbody>
                                </VTable>
                              </template>
                              <!-- checkbox content -->
                              <template v-else-if="isCheckboxContent(sub.value)">
                                <div class="review-checkbox-chips">
                                  <VChip
                                    v-for="(label, idx) in sub.value.selectedCheckbox"
                                    :key="idx"
                                    size="small"
                                    class="ma-1"
                                  >
                                    {{ label }}
                                  </VChip>
                                </div>
                              </template>
                              <template v-else-if="!isComplexValue(sub.value)">
                                <span>{{ formatPrimitive(sub.value) }}</span>
                              </template>
                              <template v-else>
                                <span>{{ JSON.stringify(sub.value, null, 2) }}</span>
                              </template>
                            </div>
                          </template>
                        </div>
                        <div v-else>
                          {{ formatPrimitive(schedule.processedContent) }}
                        </div>
                      </VExpansionPanelText>
                    </VExpansionPanel>
                  </VExpansionPanels>
                </div>
              </div>
              </div>
            </template>
          </template>

          <template v-else-if="selectedSection === 'taxReturn'">
            <div v-if="!taxReturnRows.length" class="text-medium-emphasis">No data to display.</div>
            <div v-else class="review-section">
              <div class="tax-return-print-button">
                <VBtn 
                  title="Print tax return information"
                  color="primary"
                  size="x-small"
                  icon="ri-printer-line"
                  @click.stop.prevent="printTaxReturnInformation"
                />
              </div>
              <template v-for="row in taxReturnRows" :key="row.key">
                <div class="tax-return-list">
                  <div>
                    <div v-if="isTaxReturnFieldList(row.value) && row.value.length" class="review-tai-list">
                      <div class="review-tai-row review-tai-header">
                        <span class="review-tai-col-no">Tax Return No.</span>
                        <span class="review-tai-col-field">Field</span>
                        <span class="review-tai-col-value">Value</span>
                        <span class="review-tai-col-ref">Tax return ref.</span>
                        <span class="review-tai-col-action" />
                      </div>
                      <VDivider />
                      
                      <div
                        v-for="(field, idx) in row.value"
                        :key="`${row.key}-${field.name ?? idx}`"
                        class="review-tai-row"
                      >
                        <span class="review-tai-col-no text-body-2 text-medium-emphasis">
                          <VChip class="review-tai-col-no-chip" label>{{ field.tax_return_number || '-' }}</VChip>
                        </span>

                        <span class="review-tai-col-field text-body-2">{{ field.name || '-' }}</span>

                        <span class="review-tai-col-value text-body-2">
                          {{ formatTaxReturnPrintValue(field.value, field.type) }}
                        </span>

                        <span class="review-tai-col-ref text-body-2 text-medium-emphasis">
                          <VChip class="review-tai-col-no-chip" label>{{ field.tax_return_reference || '-' }}</VChip>
                        </span>

                        <div class="review-tai-col-action d-flex align-center justify-center">
                          <VTooltip location="left" max-width="280">
                            <template #activator="{ props: tooltipProps }">
                              <VBtn v-bind="tooltipProps" icon size="x-small" variant="text">
                                <VIcon icon="ri-eye-line" size="16" />
                              </VBtn>
                            </template>
                            <div class="review-tai-tooltip-content">
                              <div class="review-tai-tooltip-row">
                                <span class="review-tai-tooltip-key">Aqua mapping:</span>
                                <span class="review-tai-tooltip-val">{{ field.aqua_mapping || '-' }}</span>
                              </div>
                              <div class="review-tai-tooltip-row">
                                <span class="review-tai-tooltip-key">IRD mapping:</span>
                                <span class="review-tai-tooltip-val">{{ field.ird_mapping || '-' }}</span>
                              </div>
                              <div class="review-tai-tooltip-row">
                                <span class="review-tai-tooltip-key">Tax return no.:</span>
                                <span class="review-tai-tooltip-val">{{ field.tax_return_number || '-' }}</span>
                              </div>
                              <div class="review-tai-tooltip-row">
                                <span class="review-tai-tooltip-key">Tax return ref.:</span>
                                <span class="review-tai-tooltip-val">{{ field.tax_return_reference || '-' }}</span>
                              </div>
                            </div>
                          </VTooltip>
                        </div>
                      </div>
                    </div>
                    <div v-else-if="isTaxReturnFieldList(row.value)" class="text-medium-emphasis">
                      No data to display.
                    </div>
                    <div v-else>
                      <span>{{ JSON.stringify(row.value, null, 2) }}</span>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </template>

          <template v-else-if="selectedSection === 'attachments'">
            <div v-if="isDebugMode" class="text-body-2 mb-2">
              {{ isDebugMode ? `(Dev)Attachment UUID: ${attachmentData?.uuid} | workingRecordUuid: ${props.workingRecordUuid}` : '-' }}
            </div>
            <VBtn color="primary" size="small" @click="openOneDrive" class="mb-2" :loading="isOneDriveButtonLoading">Open In oneDrive</VBtn>
            <FileUploadZone v-model="attachmentList" />
          </template>

        </VCardText>
      </VCard>
    </div>
  </div>
</template>

<style scoped lang="scss">
.review-layout {
  display: flex;
  height: 50vh;
}

.review-nav {
  flex-shrink: 0;
  width: 240px;
  padding: 10px;
  border-inline-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.review-main {
  flex: 1 1 auto;
  min-width: 0;
  padding: 16px;
  overflow-y: auto;
}

.review-card {
  height: 100%;
  min-height: 200px;
}

.review-card-content {
  padding: 20px;
}

.review-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-row-stacked {
  display: flex;
  flex-direction: column;
  gap: 6px;

  .review-key {
    margin-bottom: 0;
  }
}

.review-row-stacked-content {
  width: 100%;
  min-width: 0;
}

.review-grid {
  display: grid;
  grid-template-columns: minmax(0, 200px) minmax(0, 1fr);
  column-gap: 12px;
  row-gap: 12px;

  &.nested {
    grid-template-columns: minmax(0, 150px) minmax(0, 1fr);
  }
}

.review-checkbox-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-block: 2px;
}

.review-key {
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.review-value {
  white-space: pre-wrap;
  word-break: break-word;
}

.review-data-table {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  table-layout: fixed;
  width: 100%;

  th, td {
    padding: 6px 12px;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }

  .review-col-name {
    width: auto;
    text-align: left;
  }

  .review-col-sch {
    width: 100px;
    min-width: 100px;
    text-align: center;
  }

  .review-col-amount {
    width: 150px;
    min-width: 150px;
    text-align: right;
  }
}

.review-basic-expansion-panels {
  :deep(.v-expansion-panel) {
    margin-bottom: 2px;
  }
}

.review-tai-list {
  display: block;
  max-height: 40vh;
  overflow-y: auto;
}

.review-tai-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding-block: 6px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));

  &:last-child {
    border-bottom: none;
  }

  &.review-tai-header {
    position: sticky;
    top: 0;
    z-index: 1;
    min-height: 48px;
    padding-block: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    line-height: 1.25;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
    letter-spacing: 0.02em;
    background: rgb(var(--v-theme-surface));
  }
}

.review-tai-header .review-tai-col-no,
.review-tai-header .review-tai-col-field,
.review-tai-header .review-tai-col-value,
.review-tai-header .review-tai-col-ref,
.review-tai-header .review-tai-col-action {
  align-self: center;
}

.review-tai-header .review-tai-col-ref {
  justify-content: center;
  text-align: center;
}

.review-tai-col-no {
  flex: 0 0 80px;
  width: 80px;
  word-break: break-word;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.review-tai-col-no-chip {
  width: 65px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.review-tai-col-field {
  flex: 1 1 0;
  min-width: 0;
  display: block;
  line-height: 1.4;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.review-tai-col-value {
  flex: 0 0 200px;
  width: 200px;
  display: block;
  line-height: 1.4;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.review-tai-col-ref {
  flex: 0 0 90px;
  width: 90px;
  min-width: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.review-tai-col-action {
  flex: 0 0 36px;
  width: 36px;
}

.review-tai-tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 2px 0;
  font-size: 0.75rem;
}

.review-tai-tooltip-row {
  display: flex;
  gap: 6px;
}

.review-tai-tooltip-key {
  flex: 0 0 auto;
  font-weight: 600;
  white-space: nowrap;
  opacity: 0.85;
}

.review-tai-tooltip-val {
  word-break: break-all;
}

.tax-return-print-button {
  flex: 0 0 auto;
}

.tax-return-list {
  max-height: 34vh;
  overflow: hidden;
}

.tax-return-list .review-tai-list {
  max-height: 34vh;
}
</style>

