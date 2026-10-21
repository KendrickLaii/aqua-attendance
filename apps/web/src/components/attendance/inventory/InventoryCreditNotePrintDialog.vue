<script setup lang="ts">
import type { InventoryCreditNotePrintDoc } from '@/api/attendance/inventoryInvoicing'

defineProps<{ doc: InventoryCreditNotePrintDoc | null }>()

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
        <span>Credit Note {{ doc.scn_no }}</span>
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
          @click="open = false"
        />
      </VCardTitle>
      <VCardText>
        <div class="credit-print pa-4">
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
              {{ doc.location_phone }}
            </div>
            <div class="text-h6 font-weight-bold mt-4">
              CREDIT NOTE 貸項單
            </div>
            <div
              v-if="doc.status === 'void'"
              class="text-error font-weight-bold"
            >
              VOID 作廢
            </div>
          </div>

          <div class="d-flex justify-space-between mb-4">
            <div>
              <div class="text-caption text-medium-emphasis">
                Credit to 客戶
              </div>
              <div class="font-weight-medium">
                {{ doc.customer_name_zh || doc.buyer_name }}
              </div>
              <div
                v-if="doc.customer_name_en"
                class="text-body-2"
              >
                {{ doc.customer_name_en }}
              </div>
              <div
                v-if="doc.customer_code"
                class="text-body-2"
              >
                {{ doc.customer_code }}
              </div>
            </div>
            <div class="text-end">
              <div><span class="text-medium-emphasis">CN No:</span> {{ doc.scn_no }}</div>
              <div><span class="text-medium-emphasis">Invoice:</span> {{ doc.invoice_no || '—' }}</div>
              <div><span class="text-medium-emphasis">Date:</span> {{ doc.credit_date }}</div>
            </div>
          </div>

          <table class="doc-table">
            <thead>
              <tr>
                <th>Item 品項</th>
                <th class="text-end">
                  Qty
                </th>
                <th class="text-end">
                  Unit amount
                </th>
                <th class="text-end">
                  Amount
                </th>
                <th class="text-center">
                  Restock
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
                  {{ fmtMoney(line.unit_amount) }}
                </td>
                <td class="text-end">
                  {{ fmtMoney(line.amount) }}
                </td>
                <td class="text-center">
                  {{ line.restock ? 'Yes' : 'No' }}
                </td>
              </tr>
            </tbody>
          </table>

          <div class="d-flex justify-end mt-4">
            <table class="doc-totals">
              <tbody>
                <tr class="font-weight-bold">
                  <td>Total credit</td>
                  <td class="text-end">
                    {{ fmtMoney(doc.total) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="mt-4 text-body-2">
            <span class="text-medium-emphasis">Reason:</span> {{ doc.reason }}
          </div>
        </div>
      </VCardText>
    </VCard>
  </VDialog>
</template>

<style scoped>
.doc-table {
  width: 100%;
  border-collapse: collapse;
}

.doc-table th,
.doc-table td {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.doc-totals td {
  padding: 2px 8px;
}
</style>

<style>
@media print {
  body * {
    visibility: hidden;
  }

  .credit-print,
  .credit-print * {
    visibility: visible;
  }

  .credit-print {
    position: absolute;
    inset: 0;
    padding: 24px;
    background: white;
    color: black;
  }
}
</style>
