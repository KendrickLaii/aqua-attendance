<script setup lang="ts">
import {
  generateTuitionInvoices,
  listAllTuitionInvoices,
  updateTuitionInvoice,
  type TuitionInvoice,
} from '@/api/attendance/tuitionInvoices'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()
const {
  yearMonth,
  parsed: parsedYearMonth,
  monthLabel,
  changeMonth,
  toCurrentMonth,
} = useYearMonth()

const invoices = ref<TuitionInvoice[]>([])
const loading = ref(true)
const generating = ref(false)
const loadError = ref('')
const generateError = ref('')
const generateSuccess = ref('')
const expandedId = ref<string | null>(null)
const statusUpdatingId = ref<string | null>(null)
const voidTarget = ref<TuitionInvoice | null>(null)
const voidConfirmOpen = ref(false)

useAutoClearAlerts(loadError)
useAutoClearAlerts(generateError)

const statusColor: Record<string, string> = {
  draft: 'warning',
  issued: 'info',
  paid: 'success',
  void: 'grey',
}

function formatAmount(value: number): string {
  return Number(value).toFixed(2)
}

function billingLabel(unit: string): string {
  return unit === 'per_session' ? '堂費' : '月費'
}

async function loadInvoices() {
  if (!parsedYearMonth.value)
    return

  loading.value = true
  loadError.value = ''
  try {
    const result = await listAllTuitionInvoices({
      year: parsedYearMonth.value.year,
      month: parsedYearMonth.value.month,
    })

    invoices.value = result.items
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Could not load invoices.')
  }
  finally {
    loading.value = false
  }
}

async function generate() {
  if (!parsedYearMonth.value)
    return

  generating.value = true
  generateError.value = ''
  generateSuccess.value = ''
  try {
    const result = await generateTuitionInvoices(
      parsedYearMonth.value.year,
      parsedYearMonth.value.month,
    )

    generateSuccess.value = `Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}, deleted ${result.deleted ?? 0}.`
    await loadInvoices()
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not generate invoices.')
  }
  finally {
    generating.value = false
  }
}

async function setStatus(invoice: TuitionInvoice, status: 'issued' | 'paid' | 'void') {
  statusUpdatingId.value = invoice.id
  generateError.value = ''
  try {
    const updated = await updateTuitionInvoice(invoice.id, { status })
    const idx = invoices.value.findIndex(row => row.id === invoice.id)
    if (idx !== -1)
      invoices.value[idx] = updated
    voidConfirmOpen.value = false
    voidTarget.value = null
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not update invoice.')
  }
  finally {
    statusUpdatingId.value = null
  }
}

function askVoid(invoice: TuitionInvoice) {
  voidTarget.value = invoice
  voidConfirmOpen.value = true
}

async function confirmVoid() {
  if (!voidTarget.value)
    return
  await setStatus(voidTarget.value, 'void')
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

const monthTotal = computed(() =>
  invoices.value
    .filter(row => row.status !== 'void')
    .reduce((sum, row) => sum + Number(row.total), 0),
)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  if (!yearMonth.value)
    toCurrentMonth()
  else
    await loadInvoices()
})

watch(yearMonth, () => {
  generateSuccess.value = ''
  loadInvoices()
})
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <div class="text-h5 font-weight-medium">
          Tuition invoices
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ monthLabel }} · {{ invoices.length }} bill{{ invoices.length === 1 ? '' : 's' }}
          · total {{ formatAmount(monthTotal) }} (excluding void)
        </div>
      </VCol>
      <VCol
        cols="12"
        md="auto"
        class="d-flex flex-wrap align-center gap-2 justify-md-end"
      >
        <VBtn
          icon
          variant="tonal"
          size="small"
          @click="changeMonth(-1)"
        >
          <VIcon>ri-arrow-left-s-line</VIcon>
        </VBtn>
        <VTextField
          v-model="yearMonth"
          label="Month"
          type="month"
          density="compact"
          hide-details
          style="max-width: 180px;"
        />
        <VBtn
          icon
          variant="tonal"
          size="small"
          @click="changeMonth(1)"
        >
          <VIcon>ri-arrow-right-s-line</VIcon>
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-magic-line"
          :loading="generating"
          :disabled="!parsedYearMonth"
          @click="generate"
        >
          Generate
        </VBtn>
      </VCol>
    </VRow>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="loadError = ''"
    >
      {{ loadError }}
    </VAlert>
    <VAlert
      v-if="generateError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="generateError = ''"
    >
      {{ generateError }}
    </VAlert>
    <VAlert
      v-if="generateSuccess"
      type="success"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="generateSuccess = ''"
    >
      {{ generateSuccess }}
    </VAlert>

    <VCard>
      <VCardText>
        <div class="text-body-2 text-medium-emphasis mb-4">
          Generate builds one draft per student whose class dates overlap this month.
          Monthly classes bill the SKU price once. Voided bills stay void until you Generate
          again (revives to draft if still enrolled). Not yet: per-session class counts (qty is always 1),
          sending bills on WhatsApp, or Vuexy <code>/apps/invoice</code> (demo only).
        </div>

        <div
          v-if="loading"
          class="text-center py-10"
        >
          <VProgressCircular
            indeterminate
            color="primary"
          />
        </div>

        <VTable
          v-else
          density="compact"
        >
          <thead>
            <tr>
              <th>Student</th>
              <th>Status</th>
              <th class="text-end">
                Total
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            <template
              v-for="invoice in invoices"
              :key="invoice.id"
            >
              <tr
                style="cursor: pointer;"
                @click="toggleExpand(invoice.id)"
              >
                <td>
                  {{ invoice.unit_name ?? '—' }}
                  <div class="text-caption text-medium-emphasis">
                    {{ invoice.unit_code }}
                  </div>
                </td>
                <td>
                  <VChip
                    size="x-small"
                    :color="statusColor[invoice.status] ?? 'grey'"
                  >
                    {{ invoice.status }}
                  </VChip>
                </td>
                <td class="text-end">
                  {{ formatAmount(invoice.total) }}
                </td>
                <td
                  class="text-end"
                  @click.stop
                >
                  <VBtn
                    v-if="invoice.status === 'draft'"
                    size="x-small"
                    variant="text"
                    :loading="statusUpdatingId === invoice.id"
                    @click="setStatus(invoice, 'issued')"
                  >
                    Issue
                  </VBtn>
                  <VBtn
                    v-if="invoice.status === 'issued'"
                    size="x-small"
                    variant="text"
                    :loading="statusUpdatingId === invoice.id"
                    @click="setStatus(invoice, 'paid')"
                  >
                    Mark paid
                  </VBtn>
                  <VBtn
                    v-if="invoice.status === 'draft' || invoice.status === 'issued'"
                    size="x-small"
                    variant="text"
                    color="error"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askVoid(invoice)"
                  >
                    Void
                  </VBtn>
                </td>
              </tr>
              <tr v-if="expandedId === invoice.id">
                <td colspan="4">
                  <VTable density="compact">
                    <thead>
                      <tr>
                        <th>Class</th>
                        <th>Billing</th>
                        <th class="text-end">
                          Price
                        </th>
                        <th class="text-end">
                          Qty
                        </th>
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
                        <td>{{ line.sku_code }} · {{ line.name_zh }}</td>
                        <td>{{ billingLabel(line.billing_unit) }}</td>
                        <td class="text-end">
                          {{ formatAmount(line.unit_price) }}
                        </td>
                        <td class="text-end">
                          {{ formatAmount(line.quantity) }}
                        </td>
                        <td class="text-end">
                          {{ formatAmount(line.amount) }}
                        </td>
                      </tr>
                    </tbody>
                  </VTable>
                </td>
              </tr>
            </template>
            <tr v-if="invoices.length === 0">
              <td
                colspan="4"
                class="text-center text-medium-emphasis py-8"
              >
                No invoices for this month. Enroll students with start/end dates, then click Generate.
              </td>
            </tr>
          </tbody>
        </VTable>
      </VCardText>
    </VCard>

    <AttendanceConfirmDialog
      v-model="voidConfirmOpen"
      title="Void this invoice?"
      confirm-label="Void"
      confirm-color="error"
      :loading="statusUpdatingId === voidTarget?.id"
      @confirm="confirmVoid"
      @cancel="voidTarget = null"
    >
      {{ voidTarget?.unit_name ?? voidTarget?.unit_code }} will be marked void.
      Generate will restore it to draft if the student is still enrolled this month.
    </AttendanceConfirmDialog>
  </VContainer>
</template>
