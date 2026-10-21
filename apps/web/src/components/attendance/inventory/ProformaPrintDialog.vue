<script setup lang="ts">
import type { ProformaDoc } from '@/api/attendance/inventorySales'

defineProps<{ doc: ProformaDoc | null }>()

const open = defineModel<boolean>({ default: false })

function fmtMoney(value: number | null | undefined): string {
  return (value ?? 0).toFixed(2)
}

function print() {
  window.print()
}
</script>

<template>
  <VDialog
    v-model="open"
    max-width="720"
  >
    <VCard v-if="doc">
      <VCardTitle class="d-flex align-center">
        <span>Proforma {{ doc.pf_no }}</span>
        <VSpacer />
        <VBtn
          class="no-print"
          variant="tonal"
          color="primary"
          size="small"
          prepend-icon="ri-printer-line"
          @click="print"
        >
          Print
        </VBtn>
        <VBtn
          class="no-print ms-2"
          variant="text"
          size="small"
          icon="ri-close-line"
          aria-label="Close"
          @click="open = false"
        />
      </VCardTitle>
      <VCardText>
        <div class="proforma-print pa-4">
          <div class="text-center mb-6">
            <div class="text-h5 font-weight-bold">
              {{ doc.location_name_en || doc.location_name_zh || '' }}
            </div>
            <div
              v-if="doc.location_name_zh"
              class="text-body-2"
            >
              {{ doc.location_name_zh }}
            </div>
            <div
              v-if="doc.location_address"
              class="text-body-2 text-medium-emphasis"
            >
              {{ doc.location_address }}
            </div>
            <div class="text-body-2 text-medium-emphasis">
              {{ [doc.location_phone, doc.location_email].filter(Boolean).join(' · ') }}
            </div>
            <div class="text-h6 font-weight-bold mt-4">
              PROFORMA INVOICE 形式發票
            </div>
            <div class="text-caption text-medium-emphasis">
              This is a proforma invoice, not a tax invoice.
            </div>
          </div>

          <div class="d-flex justify-space-between mb-4">
            <div>
              <div class="text-caption text-medium-emphasis">
                Bill to 客戶
              </div>
              <div class="font-weight-medium">
                {{ doc.customer_name }}
              </div>
              <div
                v-if="doc.customer_code"
                class="text-body-2"
              >
                {{ doc.customer_code }}
              </div>
              <div
                v-if="doc.customer_contact"
                class="text-body-2"
              >
                {{ doc.customer_contact }}
              </div>
              <div
                v-if="doc.customer_phone"
                class="text-body-2"
              >
                {{ doc.customer_phone }}
              </div>
              <div
                v-if="doc.customer_address"
                class="text-body-2"
              >
                {{ doc.customer_address }}
              </div>
            </div>
            <div class="text-end">
              <div><span class="text-medium-emphasis">PF No:</span> {{ doc.pf_no }}</div>
              <div><span class="text-medium-emphasis">SO:</span> {{ doc.so_no }}</div>
              <div>
                <span class="text-medium-emphasis">Issued:</span>
                {{ new Date(doc.issued_at).toLocaleDateString() }}
              </div>
              <div v-if="doc.valid_until">
                <span class="text-medium-emphasis">Valid until:</span> {{ doc.valid_until }}
              </div>
            </div>
          </div>

          <table class="pf-table">
            <thead>
              <tr>
                <th>Item 品項</th>
                <th class="text-end">
                  Qty
                </th>
                <th class="text-end">
                  Unit price
                </th>
                <th class="text-end">
                  Discount
                </th>
                <th class="text-end">
                  Amount
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="line in doc.lines"
                :key="line.id"
              >
                <td>{{ [line.sku_code, line.name_zh].filter(Boolean).join(' · ') }}</td>
                <td class="text-end">
                  {{ line.qty }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.unit_price) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.discount_amount) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.amount) }}
                </td>
              </tr>
            </tbody>
          </table>

          <div class="d-flex justify-end mt-4">
            <table class="pf-totals">
              <tbody>
                <tr>
                  <td class="text-medium-emphasis">
                    Subtotal
                  </td>
                  <td class="text-end">
                    {{ fmtMoney(doc.subtotal) }}
                  </td>
                </tr>
                <tr>
                  <td class="text-medium-emphasis">
                    Discount
                  </td>
                  <td class="text-end">
                    -{{ fmtMoney(doc.discount_amount) }}
                  </td>
                </tr>
                <tr class="font-weight-bold">
                  <td>Total</td>
                  <td class="text-end">
                    {{ fmtMoney(doc.total) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div
            v-if="doc.notes"
            class="mt-4 text-body-2"
          >
            {{ doc.notes }}
          </div>
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.pf-table {
  width: 100%;
  border-collapse: collapse;
}

.pf-table th,
.pf-table td {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.pf-totals td {
  padding: 2px 8px;
}
</style>

<style>
@media print {
  body * {
    visibility: hidden;
  }

  .proforma-print,
  .proforma-print * {
    visibility: visible;
  }

  .proforma-print {
    position: absolute;
    inset: 0;
    padding: 24px;
    background: white;
    color: black;
  }
}
</style>
