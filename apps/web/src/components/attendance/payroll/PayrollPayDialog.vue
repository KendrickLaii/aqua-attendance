<script setup lang="ts">
import type { PayrollRecord } from '@/api/attendance/payroll'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import {
  formatPayrollCurrency,
  parsePayrollCurrencyInput,
  safePayrollNumber,
} from '@/utils/payrollDisplay'

type PayAmountField = 'cheque' | 'cash'

const open = defineModel<boolean>({ required: true })
const chequeNumber = defineModel<string>('chequeNumber', { required: true })
const chequeAmount = defineModel<number>('chequeAmount', { required: true })
const cashAmount = defineModel<number>('cashAmount', { required: true })

const props = defineProps<{
  record: PayrollRecord | null
  loading: boolean
  error: string
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
  'clear-error': []
}>()

const focusedPayField = ref<PayAmountField | null>(null)
const focusedPayRaw = ref('')

const paySplitTotal = computed(() => chequeAmount.value + cashAmount.value)

function payAmountValue(field: PayAmountField) {
  return field === 'cheque' ? chequeAmount.value : cashAmount.value
}

function payAmountDisplay(field: PayAmountField) {
  if (focusedPayField.value === field)
    return focusedPayRaw.value

  return formatPayrollCurrency(payAmountValue(field))
}

function onPayAmountFocus(field: PayAmountField) {
  focusedPayField.value = field
  const n = payAmountValue(field)

  focusedPayRaw.value = Number.isFinite(n) ? String(n) : '0'
}

function onPayAmountInput(field: PayAmountField, v: string | number | null) {
  focusedPayRaw.value = v == null ? '' : String(v)
  const parsed = parsePayrollCurrencyInput(focusedPayRaw.value)

  if (field === 'cheque')
    chequeAmount.value = parsed
  else
    cashAmount.value = parsed
}

function onPayAmountBlur(field: PayAmountField) {
  const parsed = parsePayrollCurrencyInput(focusedPayRaw.value)

  if (field === 'cheque')
    chequeAmount.value = parsed
  else
    cashAmount.value = parsed

  focusedPayField.value = null
  focusedPayRaw.value = ''
}
</script>

<template>
  <AttendanceConfirmDialog
    v-model="open"
    title="Mark payroll as paid?"
    confirm-label="Pay"
    confirm-color="primary"
    :loading="props.loading"
    :error="props.error"
    :max-width="520"
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
    @clear-error="emit('clear-error')"
  >
    <template v-if="props.record">
      <div class="mb-4">
        Mark payroll as paid for
        <strong>{{ props.record.unit_name || props.record.unit_code || props.record.unit_id }}</strong>
        ({{ props.record.payroll_period_start }} – {{ props.record.payroll_period_end }})?
        Net pay
        <strong>{{ formatPayrollCurrency(props.record.net_pay) }}</strong>.
      </div>
      <VTextField
        v-model="chequeNumber"
        class="mb-3"
        label="Cheque#"
        density="compact"
        variant="outlined"
        hide-details
        autocomplete="off"
      />
      <VRow dense>
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            :model-value="payAmountDisplay('cheque')"
            class="pay-amount-field"
            label="Cheque amount"
            density="compact"
            variant="underlined"
            hide-details
            inputmode="decimal"
            @focus="onPayAmountFocus('cheque')"
            @blur="onPayAmountBlur('cheque')"
            @update:model-value="(v) => onPayAmountInput('cheque', v)"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            :model-value="payAmountDisplay('cash')"
            class="pay-amount-field"
            label="Cash amount"
            density="compact"
            variant="underlined"
            hide-details
            inputmode="decimal"
            @focus="onPayAmountFocus('cash')"
            @blur="onPayAmountBlur('cash')"
            @update:model-value="(v) => onPayAmountInput('cash', v)"
          />
        </VCol>
      </VRow>
      <div class="text-caption text-medium-emphasis mt-3">
        Cheque + Cash = {{ formatPayrollCurrency(paySplitTotal) }}
        <span v-if="Math.abs(paySplitTotal - safePayrollNumber(props.record.net_pay)) > 0.009">
          · Net {{ formatPayrollCurrency(props.record.net_pay) }}
        </span>
      </div>
    </template>
  </AttendanceConfirmDialog>
</template>

<style scoped>
.pay-amount-field :deep(input) {
  text-align: end;
}
</style>
