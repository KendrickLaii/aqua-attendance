<script setup lang="ts">
import { useDisplay } from 'vuetify'
import {
  type InventoryReceiptPaidBy,
  RECEIPT_PAID_BY_OPTIONS,
  createReceipt,
} from '@/api/attendance/inventoryInvoicing'
import { formatApiError } from '@/utils/formatApiDetail'
import { formatMoney } from '@/utils/inventoryDisplay'

export interface PaymentInvoice {
  id: string
  invoice_no: string
  buyer_name?: string | null
  balance: number
}

export interface PaymentInvoiceOption {
  value: string
  title: string
  invoice: PaymentInvoice
}

const props = defineProps<{
  modelValue: boolean
  invoice?: PaymentInvoice | null
  invoiceOptions?: PaymentInvoiceOption[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  'saved': []
}>()

const open = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

const pickedId = ref<string | null>(null)
const amount = ref<number | null>(null)
const method = ref<InventoryReceiptPaidBy>('cash')
const reference = ref('')
const date = ref('')
const display = useDisplay()
const toast = useToast()
const saving = ref(false)
const errorMsg = ref('')

const activeInvoice = computed(() => {
  if (props.invoice)
    return props.invoice

  return props.invoiceOptions?.find(o => o.value === pickedId.value)?.invoice ?? null
})

const invalid = computed(() =>
  !activeInvoice.value
  || !amount.value
  || amount.value <= 0
  || amount.value > activeInvoice.value.balance,
)

watch(open, v => {
  if (v) {
    pickedId.value = props.invoice?.id ?? null
    amount.value = props.invoice?.balance ?? null
    method.value = 'cash'
    reference.value = ''
    date.value = ''
    errorMsg.value = ''
  }
})

watch(pickedId, id => {
  const inv = props.invoiceOptions?.find(o => o.value === id)?.invoice

  if (inv)
    amount.value = inv.balance
})

async function submit() {
  const inv = activeInvoice.value
  if (!inv || invalid.value)
    return
  saving.value = true
  errorMsg.value = ''
  try {
    const receipt = await createReceipt({
      invoice_id: inv.id,
      amount: amount.value ?? 0,
      paid_by: method.value,
      reference_no: reference.value || null,
      receipt_date: date.value || null,
    })

    open.value = false
    emit('saved')
    toast.show(`Receipt ${receipt.receipt_no} posted · ${formatMoney(receipt.amount)}`)
  }
  catch (e) {
    errorMsg.value = formatApiError(e, 'Operation failed.')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <VDialog
    v-model="open"
    max-width="560"
    :fullscreen="display.xs.value"
    scrollable
  >
    <VCard>
      <VCardTitle>Record Payment 收款</VCardTitle>
      <VCardText>
        <VAlert
          v-if="errorMsg"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ errorMsg }}
        </VAlert>
        <div class="text-overline text-medium-emphasis mb-2">
          Invoice
        </div>
        <VAutocomplete
          v-if="invoiceOptions"
          v-model="pickedId"
          :items="invoiceOptions"
          label="Invoice *"
          :loading="loading"
          placeholder="Search invoice…"
        />
        <div
          v-else-if="invoice"
          class="text-body-2"
        >
          {{ invoice.invoice_no }} · {{ invoice.buyer_name }}
        </div>
        <div class="text-overline text-medium-emphasis mb-2 mt-4">
          Payment
        </div>
        <VRow>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model.number="amount"
              type="number"
              min="0"
              step="0.01"
              prefix="HK$"
              label="Amount *"
              :hint="activeInvoice ? `Balance ${formatMoney(activeInvoice.balance)}` : ''"
              persistent-hint
              :error="invalid && !!activeInvoice"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VSelect
              v-model="method"
              :items="RECEIPT_PAID_BY_OPTIONS"
              label="Paid by"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="reference"
              label="Reference no."
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
          >
            <VTextField
              v-model="date"
              type="date"
              label="Receipt date"
            />
          </VCol>
        </VRow>
      </VCardText>
      <VDivider />
      <VCardActions>
        <VSpacer />
        <VBtn
          variant="text"
          @click="open = false"
        >
          Cancel
        </VBtn>
        <VBtn
          color="primary"
          :disabled="invalid"
          :loading="saving"
          @click="submit"
        >
          Post Receipt
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
</template>
