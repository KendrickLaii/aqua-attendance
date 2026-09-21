<script setup lang="ts">
import type { TuitionInvoice } from '@/api/attendance/tuitionInvoices'
import {
  billingLabel,
  classPreview,
  formatInvoiceMoney,
  invoiceClassNames,
  invoiceLineFormula,
  invoiceOpenedBy,
  invoicePeriodLabel,
  invoiceStatusColor,
  invoiceStatusLabel,
  invoiceStudentLabel,
} from '@/utils/invoiceDisplay'

defineProps<{
  invoices: TuitionInvoice[]
  filteredInvoices: TuitionInvoice[]
  pagedInvoices: TuitionInvoice[]
  loading: boolean
  allMonths: boolean
  allLocations: boolean
  billsCaption: string
  expandedId: string | null
  statusUpdatingId: string | null
  showBillingHelp: boolean
  locationName: (id: string) => string
}>()

const emit = defineEmits<{
  'update:showBillingHelp': [value: boolean]
  'toggle-expand': [id: string]
  'row-keydown': [event: KeyboardEvent, id: string]
  print: [invoice: TuitionInvoice]
  issue: [invoice: TuitionInvoice]
  pay: [invoice: TuitionInvoice]
  void: [invoice: TuitionInvoice]
  'clear-filters': []
}>()
</script>

<template>
  <VCard>
    <VCardItem>
      <VCardTitle class="d-flex align-center flex-wrap gap-2">
        <span>Bills</span>
        <span
          v-if="billsCaption"
          class="text-caption text-medium-emphasis font-weight-regular"
        >
          {{ billsCaption }}
          <template v-if="filteredInvoices.length !== invoices.length">
            matching · {{ invoices.length }} total
          </template>
        </span>
      </VCardTitle>
      <template #append>
        <VBtn
          variant="text"
          size="small"
          :prepend-icon="showBillingHelp ? 'ri-question-fill' : 'ri-question-line'"
          @click="emit('update:showBillingHelp', !showBillingHelp)"
        >
          How billing works
        </VBtn>
      </template>
      <VCardSubtitle>
        {{ allMonths ? 'All bills. Open a row for line items.' : 'One bill per student for this calendar month. Open a row for line items.' }}
      </VCardSubtitle>
    </VCardItem>
    <VCardText>
      <VAlert
        v-if="showBillingHelp"
        variant="tonal"
        color="info"
        density="compact"
        class="mb-4"
        closable
        @click:close="emit('update:showBillingHelp', false)"
      >
        <ul class="text-body-2 ps-4 mb-0">
          <li>One draft bill per student whose classes overlap this month.</li>
          <li>Monthly classes: billed once for the month, even if they miss days.</li>
          <li>Per-class packages: billed once for the package they bought — not from attendance.</li>
          <li>Private / variable-price classes: leave the class price empty. Record how many sessions were bought, then set the price on a <strong>Manual invoice</strong>.</li>
          <li>Packages with no price yet are skipped by Generate — bill them with a manual invoice.</li>
          <li>Inactive classes and monthly classes with no price are skipped. Issued and paid bills are not changed.</li>
          <li>The Location filter shows bills for that campus. All months and All locations show every bill.</li>
        </ul>
      </VAlert>

      <div
        v-if="loading"
        class="text-center py-10"
      >
        <VProgressCircular
          indeterminate
          color="primary"
        />
        <div class="text-caption text-medium-emphasis mt-3">
          Loading bills…
        </div>
      </div>

      <div
        v-else
        class="invoices-table-scroll"
      >
        <VTable
          class="invoices-table"
          density="compact"
          hover
        >
          <thead>
            <tr>
              <th class="col-student">
                Student
              </th>
              <th class="col-no">
                No.
              </th>
              <th class="col-staff">
                Opened by
              </th>
              <th class="col-classes">
                Classes
              </th>
              <th class="col-status">
                Status
              </th>
              <th class="col-total text-end">
                Total
              </th>
              <th class="col-actions">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="invoice in pagedInvoices"
              :key="invoice.id"
            >
              <tr
                class="invoice-row"
                :class="[
                  `invoice-row--${invoice.status}`,
                  { 'invoice-row--expanded': expandedId === invoice.id },
                ]"
                tabindex="0"
                :aria-expanded="expandedId === invoice.id"
                :aria-label="`${invoiceStudentLabel(invoice)}, ${invoiceStatusLabel[invoice.status] ?? invoice.status}`"
                @click="emit('toggle-expand', invoice.id)"
                @keydown="emit('row-keydown', $event, invoice.id)"
              >
                <td class="col-student">
                  <div
                    class="student-name"
                    :title="invoiceStudentLabel(invoice)"
                  >
                    {{ invoiceStudentLabel(invoice) }}
                  </div>
                  <div class="text-caption text-medium-emphasis d-flex align-center flex-wrap gap-1">
                    <span v-if="invoice.unit_code">{{ invoice.unit_code }}</span>
                    <VChip
                      v-if="invoice.kind === 'manual'"
                      size="x-small"
                      color="info"
                      label
                    >
                      Manual
                    </VChip>
                    <span
                      v-if="allLocations && locationName(invoice.location_id)"
                      class="text-no-wrap"
                    >{{ locationName(invoice.location_id) }}</span>
                  </div>
                </td>
                <td class="col-no invoice-no">
                  <div>{{ invoice.invoice_no ?? '—' }}</div>
                  <div
                    v-if="invoice.receipt_no"
                    class="text-caption text-medium-emphasis"
                  >
                    {{ invoice.receipt_no }}
                  </div>
                </td>
                <td class="col-staff">
                  <div
                    v-if="invoiceOpenedBy(invoice)"
                    class="staff-name"
                    :title="invoiceOpenedBy(invoice)"
                  >
                    {{ invoiceOpenedBy(invoice) }}
                  </div>
                  <span
                    v-else
                    class="text-disabled"
                  >—</span>
                </td>
                <td class="col-classes">
                  <div
                    class="class-preview"
                    :title="invoiceClassNames(invoice).join(' · ') || undefined"
                  >
                    {{ classPreview(invoice) }}
                  </div>
                  <div class="text-caption text-medium-emphasis text-truncate">
                    {{ invoicePeriodLabel(invoice) }}
                    · {{ invoice.lines.length }} line{{ invoice.lines.length === 1 ? '' : 's' }}
                    <VIcon
                      size="14"
                      class="ms-1"
                      aria-hidden="true"
                    >
                      {{ expandedId === invoice.id ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line' }}
                    </VIcon>
                  </div>
                </td>
                <td class="col-status">
                  <VChip
                    size="x-small"
                    label
                    :color="invoiceStatusColor[invoice.status] ?? 'grey'"
                  >
                    {{ invoiceStatusLabel[invoice.status] ?? invoice.status }}
                  </VChip>
                </td>
                <td class="col-total text-end font-weight-medium tabular-nums">
                  {{ formatInvoiceMoney(Number(invoice.total)) }}
                </td>
                <td
                  class="col-actions text-end"
                  @click.stop
                >
                  <VBtn
                    v-if="invoice.status !== 'void'"
                    icon="ri-printer-line"
                    size="x-small"
                    variant="text"
                    aria-label="Print invoice"
                    title="Print / reprint"
                    @click="emit('print', invoice)"
                  />
                  <VBtn
                    v-if="invoice.status === 'draft'"
                    icon="ri-file-check-line"
                    size="x-small"
                    variant="text"
                    color="primary"
                    aria-label="Issue bill"
                    title="Issue bill"
                    :loading="statusUpdatingId === invoice.id"
                    @click="emit('issue', invoice)"
                  />
                  <VBtn
                    v-if="invoice.status === 'issued'"
                    icon="ri-money-dollar-circle-line"
                    size="x-small"
                    variant="text"
                    color="success"
                    aria-label="Mark paid"
                    title="Mark paid — open a receipt"
                    @click="emit('pay', invoice)"
                  />
                  <VBtn
                    v-if="invoice.status === 'draft' || invoice.status === 'issued'"
                    icon="ri-close-circle-line"
                    size="x-small"
                    variant="text"
                    color="error"
                    aria-label="Cancel this bill"
                    title="Cancel this bill"
                    :loading="statusUpdatingId === invoice.id"
                    @click="emit('void', invoice)"
                  />
                </td>
              </tr>
              <tr
                v-if="expandedId === invoice.id"
                class="invoice-detail-row"
              >
                <td colspan="7">
                  <div class="invoice-slip">
                    <div class="invoice-slip__meta">
                      <span>
                        {{ invoice.kind === 'manual'
                          ? 'Manual invoice — lines were typed when it was issued.'
                          : 'Prices were copied when this bill was made. Changing the class later does not change issued or paid bills.' }}
                      </span>
                      <span>Period: {{ invoicePeriodLabel(invoice) }}</span>
                      <span v-if="invoiceOpenedBy(invoice)">
                        Opened by <strong>{{ invoiceOpenedBy(invoice) }}</strong>
                      </span>
                      <span v-if="invoice.notes">
                        Remark: {{ invoice.notes }}
                      </span>
                    </div>
                    <VTable
                      density="compact"
                      class="invoice-lines"
                    >
                      <thead>
                        <tr>
                          <th>Class</th>
                          <th>Teacher</th>
                          <th>How billed</th>
                          <th>Calculation</th>
                          <th class="text-end">
                            Amount
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="line in invoice.lines"
                          :key="line.id"
                        >
                          <td>
                            {{ line.name_zh }}
                            <div class="text-caption text-medium-emphasis">
                              {{ line.sku_code }}
                            </div>
                          </td>
                          <td class="text-body-2">
                            {{ line.staff_name || '—' }}
                          </td>
                          <td>
                            <VChip
                              size="x-small"
                              variant="tonal"
                              label
                            >
                              {{ billingLabel(line.billing_unit) }}
                            </VChip>
                          </td>
                          <td class="text-medium-emphasis tabular-nums">
                            {{ invoiceLineFormula(line) }}
                          </td>
                          <td class="text-end font-weight-medium text-no-wrap tabular-nums">
                            {{ formatInvoiceMoney(Number(line.amount)) }}
                          </td>
                        </tr>
                        <tr v-if="invoice.lines.length === 0">
                          <td
                            colspan="5"
                            class="text-medium-emphasis"
                          >
                            No chargeable classes this month.
                          </td>
                        </tr>
                      </tbody>
                    </VTable>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="!loading && filteredInvoices.length === 0">
              <td
                colspan="7"
                class="text-center py-10"
              >
                <div class="invoice-empty">
                  <VIcon
                    size="36"
                    class="mb-2 text-medium-emphasis"
                    aria-hidden="true"
                  >
                    ri-file-list-3-line
                  </VIcon>
                  <template v-if="invoices.length === 0">
                    <div class="text-body-1 font-weight-medium">
                      {{ allMonths ? 'No bills yet' : 'No bills this month' }}
                    </div>
                    <div class="text-medium-emphasis mt-1">
                      <template v-if="allMonths">
                        Pick a month and generate, or create a manual invoice.
                      </template>
                      <template v-else>
                        Enroll students with billed dates (and packages bought for per-class courses), then Generate.
                      </template>
                    </div>
                  </template>
                  <template v-else>
                    <div class="text-body-1 font-weight-medium">
                      No bills match this search or status
                    </div>
                    <VBtn
                      class="mt-3"
                      size="small"
                      variant="tonal"
                      prepend-icon="ri-filter-off-line"
                      @click="emit('clear-filters')"
                    >
                      Clear filters
                    </VBtn>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <slot name="pagination" />
    </VCardText>
  </VCard>
</template>

<style scoped lang="scss">
.invoices-table-scroll {
  overflow-x: hidden;
}

.invoices-table {
  width: 100%;
  table-layout: fixed;
}

.invoices-table :deep(thead th),
.invoices-table :deep(tbody td) {
  vertical-align: middle;
}

.invoices-table :deep(thead th) {
  white-space: nowrap;
}

.invoices-table :deep(.col-student) {
  width: 18%;
  padding-left: 12px;
}

.invoices-table :deep(.col-no) {
  width: 7%;
}

.invoices-table :deep(.col-staff) {
  width: 12%;
}

.invoices-table :deep(.col-classes) {
  width: 28%;
}

.invoices-table :deep(.col-status) {
  width: 9%;
}

.invoices-table :deep(.col-total) {
  width: 12%;
}

.invoices-table :deep(.col-actions) {
  width: 14%;
  white-space: nowrap;
}

.invoices-table :deep(.student-name),
.invoices-table :deep(.class-preview),
.invoices-table :deep(.staff-name) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.invoices-table :deep(.student-name) {
  font-weight: 500;
}

.invoices-table :deep(.col-no),
.invoices-table :deep(.col-status),
.invoices-table :deep(.col-total) {
  white-space: nowrap;
}

.invoice-no,
.tabular-nums {
  font-variant-numeric: tabular-nums;
}

.invoice-no {
  letter-spacing: 0.02em;
  font-weight: 600;
}

.invoice-row {
  cursor: pointer;
}

.invoice-row td:first-child {
  box-shadow: inset 3px 0 0 rgba(var(--v-theme-on-surface), 0.16);
}

.invoice-row--draft td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-warning));
}

.invoice-row--issued td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-info));
}

.invoice-row--paid td:first-child {
  box-shadow: inset 3px 0 0 rgb(var(--v-theme-success));
}

.invoice-row--void {
  opacity: 0.72;
}

.invoice-row--void td:first-child {
  box-shadow: inset 3px 0 0 rgba(var(--v-theme-on-surface), 0.28);
}

.invoice-row--expanded {
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.invoice-row:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -2px;
}

.invoice-detail-row td {
  background: rgba(var(--v-theme-on-surface), 0.03);
  padding-block: 12px !important;
}

.invoice-slip {
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 10px;
  padding: 12px 14px;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-on-surface), 0.02), transparent 48px),
    rgb(var(--v-theme-surface));
}

.invoice-slip__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 10px;
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.75rem;
  line-height: 1.4;
}

.invoice-lines {
  background: transparent;
}

.invoice-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 28rem;
  margin-inline: auto;
}

@media (prefers-reduced-motion: reduce) {
  .invoice-row {
    transition: none;
  }
}
</style>
