<script setup lang="ts">
import type { InventoryReceiptPrintDoc } from '@/api/attendance/inventoryInvoicing'

defineProps<{ doc: InventoryReceiptPrintDoc | null }>()

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
    max-width="600"
  >
    <VCard v-if="doc">
      <VCardTitle class="d-flex align-center">
        <span>Receipt {{ doc.receipt_no }}</span>
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
        <div class="receipt-print pa-4">
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
              RECEIPT 收據
            </div>
            <div
              v-if="doc.status === 'void'"
              class="text-error font-weight-bold"
            >
              VOID 作廢
            </div>
          </div>

          <table class="doc-fields">
            <tbody>
              <tr>
                <td class="text-medium-emphasis">
                  Receipt No
                </td>
                <td>{{ doc.receipt_no }}</td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">
                  Date
                </td>
                <td>{{ doc.receipt_date }}</td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">
                  Received from 客戶
                </td>
                <td>{{ doc.customer_name_zh || doc.buyer_name }}<span v-if="doc.customer_name_en"> ({{ doc.customer_name_en }})</span></td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">
                  Invoice
                </td>
                <td>{{ doc.invoice_no || '—' }}</td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">
                  Paid by
                </td>
                <td>{{ doc.paid_by }}<span v-if="doc.reference_no"> · {{ doc.reference_no }}</span></td>
              </tr>
            </tbody>
          </table>

          <div class="amount-box text-center my-6">
            <div class="text-caption text-medium-emphasis">
              Amount received 金額
            </div>
            <div class="text-h4 font-weight-bold">
              {{ fmtMoney(doc.amount) }}
            </div>
          </div>

          <table class="doc-fields">
            <tbody>
              <tr>
                <td class="text-medium-emphasis">
                  Invoice total
                </td>
                <td class="text-end">
                  {{ fmtMoney(doc.invoice_total) }}
                </td>
              </tr>
              <tr>
                <td class="text-medium-emphasis">
                  Paid to date
                </td>
                <td class="text-end">
                  {{ fmtMoney(doc.invoice_paid_total) }}
                </td>
              </tr>
              <tr class="font-weight-bold">
                <td>Balance</td>
                <td class="text-end">
                  {{ fmtMoney(doc.invoice_balance) }}
                </td>
              </tr>
            </tbody>
          </table>

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
.doc-fields {
  width: 100%;
  border-collapse: collapse;
}

.doc-fields td {
  padding: 4px 8px;
}

.amount-box {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  padding: 16px;
}
</style>

<style>
@media print {
  body * {
    visibility: hidden;
  }

  .receipt-print,
  .receipt-print * {
    visibility: visible;
  }

  .receipt-print {
    position: absolute;
    inset: 0;
    padding: 24px;
    background: white;
    color: black;
  }
}
</style>
