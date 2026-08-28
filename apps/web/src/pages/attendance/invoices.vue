<script setup lang="ts">
import {
  generateTuitionInvoices,
  listAllTuitionInvoices,
  updateTuitionInvoice,
  type TuitionInvoice,
  type TuitionInvoiceLine,
  type TuitionInvoiceStatus,
} from '@/api/attendance/tuitionInvoices'
import StatCards from '@/components/attendance/StatCards.vue'
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
const pendingStatus = ref<{ invoice: TuitionInvoice; status: 'issued' | 'paid' | 'void' } | null>(null)
const pendingGenerate = ref(false)
const searchQuery = ref('')
const statusFilter = ref<'all' | TuitionInvoiceStatus>('all')

useAutoClearAlerts(loadError)
useAutoClearAlerts(generateError)

const statusColor: Record<string, string> = {
  draft: 'warning',
  issued: 'info',
  paid: 'success',
  void: 'grey',
}

const statusFilters: { title: string; value: 'all' | TuitionInvoiceStatus }[] = [
  { title: 'All', value: 'all' },
  { title: 'Draft', value: 'draft' },
  { title: 'Issued', value: 'issued' },
  { title: 'Paid', value: 'paid' },
  { title: 'Void', value: 'void' },
]

function formatMoney(value: number): string {
  return `HK$${Number(value).toLocaleString('en-HK', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function billingLabel(unit: string): string {
  return unit === 'per_session' ? '堂費' : '月費'
}

function formatQty(line: TuitionInvoiceLine): string {
  const qty = Number(line.quantity)
  const whole = Number.isInteger(qty) ? String(qty) : qty.toFixed(2)
  if (line.billing_unit === 'per_session')
    return `${whole} ${qty === 1 ? 'session' : 'sessions'}`

  return qty === 1 ? '1 month' : `${whole} months`
}

function lineFormula(line: TuitionInvoiceLine): string {
  return `${formatQty(line)} × ${formatMoney(Number(line.unit_price))}`
}

function classNames(invoice: TuitionInvoice): string[] {
  return invoice.lines.map(line => line.name_zh || line.sku_code)
}

function classPreview(invoice: TuitionInvoice): string {
  const names = classNames(invoice)
  if (names.length === 0)
    return 'No lines'
  if (names.length <= 2)
    return names.join(' · ')

  return `${names.slice(0, 2).join(' · ')} +${names.length - 2}`
}

const statusTotals = computed(() => {
  const totals = {
    draft: { count: 0, amount: 0 },
    issued: { count: 0, amount: 0 },
    paid: { count: 0, amount: 0 },
    void: { count: 0, amount: 0 },
  }
  for (const invoice of invoices.value) {
    const bucket = totals[invoice.status]
    if (!bucket)
      continue
    bucket.count += 1
    bucket.amount += Number(invoice.total)
  }
  return totals
})

const collectibleTotal = computed(
  () => statusTotals.value.draft.amount + statusTotals.value.issued.amount,
)

const filteredInvoices = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return invoices.value.filter((invoice) => {
    if (statusFilter.value !== 'all' && invoice.status !== statusFilter.value)
      return false
    if (!query)
      return true
    const haystack = [
      invoice.unit_name,
      invoice.unit_code,
      ...invoice.lines.flatMap(line => [line.sku_code, line.name_zh]),
    ].join(' ').toLowerCase()

    return haystack.includes(query)
  })
})

const statCards = computed(() => [
  {
    label: 'To collect',
    value: formatMoney(collectibleTotal.value),
    hint: `${statusTotals.value.draft.count} draft · ${statusTotals.value.issued.count} issued`,
    icon: 'ri-wallet-3-line',
    color: 'primary',
  },
  {
    label: 'Paid',
    value: formatMoney(statusTotals.value.paid.amount),
    hint: `${statusTotals.value.paid.count} paid this month`,
    icon: 'ri-checkbox-circle-line',
    color: 'success',
  },
  {
    label: 'Drafts',
    value: String(statusTotals.value.draft.count),
    hint: formatMoney(statusTotals.value.draft.amount),
    icon: 'ri-draft-line',
    color: 'warning',
  },
  {
    label: 'Bills',
    value: String(invoices.value.length),
    hint: statusTotals.value.void.count ? `${statusTotals.value.void.count} void excluded from collect` : monthLabel.value,
    icon: 'ri-file-list-3-line',
    color: 'info',
  },
])

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

function askGenerate() {
  if (!parsedYearMonth.value)
    return
  pendingGenerate.value = true
}

async function confirmGenerate() {
  await generate()
  pendingGenerate.value = false
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
    pendingStatus.value = null
  }
  catch (e) {
    generateError.value = formatApiError(e, 'Could not update invoice.')
  }
  finally {
    statusUpdatingId.value = null
  }
}

function askStatus(invoice: TuitionInvoice, status: 'issued' | 'paid' | 'void') {
  pendingStatus.value = { invoice, status }
}

async function confirmPendingStatus() {
  if (!pendingStatus.value)
    return
  await setStatus(pendingStatus.value.invoice, pendingStatus.value.status)
}

const statusConfirmTitle = computed(() => {
  const status = pendingStatus.value?.status
  if (status === 'issued')
    return 'Issue this invoice?'
  if (status === 'paid')
    return 'Mark this invoice paid?'
  if (status === 'void')
    return 'Void this invoice?'

  return 'Update invoice?'
})

const statusConfirmLabel = computed(() => {
  const status = pendingStatus.value?.status
  if (status === 'issued')
    return 'Issue'
  if (status === 'paid')
    return 'Mark paid'
  if (status === 'void')
    return 'Void'

  return 'Confirm'
})

const statusConfirmColor = computed(() => pendingStatus.value?.status === 'void' ? 'error' : 'primary')

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

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
  expandedId.value = null
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
          {{ monthLabel }}
          <span v-if="invoices.length">
            · {{ invoices.length }} bill{{ invoices.length === 1 ? '' : 's' }}
            · {{ formatMoney(collectibleTotal) }} to collect
          </span>
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
          @click="askGenerate"
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

    <StatCards
      v-if="!loading"
      :cards="statCards"
    />

    <VCard>
      <VCardItem>
        <VCardTitle>Bills</VCardTitle>
        <VCardSubtitle>
          One bill per student for this calendar month. Click a row for line items.
        </VCardSubtitle>
        <template #append>
          <div class="d-flex flex-wrap align-center gap-2">
            <VChipGroup
              v-model="statusFilter"
              mandatory
              selected-class="text-primary"
            >
              <VChip
                v-for="chip in statusFilters"
                :key="chip.value"
                :value="chip.value"
                size="small"
                variant="outlined"
                filter
              >
                {{ chip.title }}
              </VChip>
            </VChipGroup>
            <VTextField
              v-model="searchQuery"
              placeholder="Student, code, or class"
              prepend-inner-icon="ri-search-line"
              density="compact"
              hide-details
              clearable
              style="min-width: 220px;"
            />
          </div>
        </template>
      </VCardItem>
      <VCardText>
        <VExpansionPanels
          variant="accordion"
          class="mb-4"
        >
          <VExpansionPanel title="How Generate bills this month">
            <VExpansionPanelText>
              <ul class="text-body-2 ps-4 mb-0">
                <li>One draft per student whose enroll dates overlap this month.</li>
                <li>月費: SKU price once, even if they miss days.</li>
                <li>堂費: price × SKU class days they scanned at the class location (Hong Kong calendar day). No scan = no line. New 堂費 classes must have at least one class day.</li>
                <li>Legacy 堂費 with no class days still bills qty 1 and ignores attendance.</li>
                <li>Inactive classes and unpriced classes are skipped. Issued / paid bills are not overwritten.</li>
              </ul>
            </VExpansionPanelText>
          </VExpansionPanel>
        </VExpansionPanels>

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
          hover
        >
          <thead>
            <tr>
              <th>Student</th>
              <th>Classes</th>
              <th>Period</th>
              <th>Status</th>
              <th class="text-end">
                Total
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            <template
              v-for="invoice in filteredInvoices"
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
                  <div>{{ classPreview(invoice) }}</div>
                  <div class="text-caption text-medium-emphasis">
                    {{ invoice.lines.length }} line{{ invoice.lines.length === 1 ? '' : 's' }}
                    <VIcon
                      size="14"
                      class="ms-1"
                    >
                      {{ expandedId === invoice.id ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line' }}
                    </VIcon>
                  </div>
                </td>
                <td class="text-caption text-medium-emphasis text-no-wrap">
                  {{ invoice.period_start }} – {{ invoice.period_end }}
                </td>
                <td>
                  <VChip
                    size="x-small"
                    :color="statusColor[invoice.status] ?? 'grey'"
                  >
                    {{ invoice.status }}
                  </VChip>
                </td>
                <td class="text-end font-weight-medium text-no-wrap">
                  {{ formatMoney(Number(invoice.total)) }}
                </td>
                <td
                  class="text-end text-no-wrap"
                  @click.stop
                >
                  <VBtn
                    v-if="invoice.status === 'draft'"
                    size="x-small"
                    variant="text"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askStatus(invoice, 'issued')"
                  >
                    Issue
                  </VBtn>
                  <VBtn
                    v-if="invoice.status === 'issued'"
                    size="x-small"
                    variant="text"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askStatus(invoice, 'paid')"
                  >
                    Mark paid
                  </VBtn>
                  <VBtn
                    v-if="invoice.status === 'draft' || invoice.status === 'issued'"
                    size="x-small"
                    variant="text"
                    color="error"
                    :loading="statusUpdatingId === invoice.id"
                    @click="askStatus(invoice, 'void')"
                  >
                    Void
                  </VBtn>
                </td>
              </tr>
              <tr v-if="expandedId === invoice.id">
                <td colspan="6">
                  <div class="text-caption text-medium-emphasis mb-2">
                    Snapshot of SKU price at Generate. Changing the class later does not rewrite issued or paid bills.
                  </div>
                  <VTable density="compact">
                    <thead>
                      <tr>
                        <th>Class</th>
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
                        <td>
                          <VChip
                            size="x-small"
                            variant="tonal"
                          >
                            {{ billingLabel(line.billing_unit) }}
                          </VChip>
                        </td>
                        <td class="text-medium-emphasis">
                          {{ lineFormula(line) }}
                        </td>
                        <td class="text-end font-weight-medium text-no-wrap">
                          {{ formatMoney(Number(line.amount)) }}
                        </td>
                      </tr>
                      <tr v-if="invoice.lines.length === 0">
                        <td
                          colspan="4"
                          class="text-medium-emphasis"
                        >
                          No chargeable classes this month.
                        </td>
                      </tr>
                    </tbody>
                  </VTable>
                </td>
              </tr>
            </template>
            <tr v-if="!loading && filteredInvoices.length === 0">
              <td
                colspan="6"
                class="text-center text-medium-emphasis py-8"
              >
                <template v-if="invoices.length === 0">
                  No bills this month. Enroll students with start/end dates, set class days and price on 堂費 classes, then Generate.
                </template>
                <template v-else>
                  No bills match this search or status.
                </template>
              </td>
            </tr>
          </tbody>
        </VTable>
      </VCardText>
    </VCard>

    <AttendanceConfirmDialog
      :model-value="pendingStatus != null"
      :title="statusConfirmTitle"
      :confirm-label="statusConfirmLabel"
      :confirm-color="statusConfirmColor"
      :loading="statusUpdatingId === pendingStatus?.invoice.id"
      @update:model-value="value => { if (!value) pendingStatus = null }"
      @confirm="confirmPendingStatus"
      @cancel="pendingStatus = null"
    >
      <template v-if="pendingStatus?.status === 'issued'">
        Issuing locks {{ pendingStatus.invoice.unit_name ?? pendingStatus.invoice.unit_code }}
        at {{ formatMoney(Number(pendingStatus.invoice.total)) }}. Generate will no longer change this month.
      </template>
      <template v-else-if="pendingStatus?.status === 'paid'">
        Mark {{ pendingStatus.invoice.unit_name ?? pendingStatus.invoice.unit_code }}
        ({{ formatMoney(Number(pendingStatus.invoice.total)) }}) as paid?
      </template>
      <template v-else-if="pendingStatus?.status === 'void'">
        {{ pendingStatus.invoice.unit_name ?? pendingStatus.invoice.unit_code }} will be marked void.
        Generate will restore it to draft if the student is still enrolled this month.
      </template>
    </AttendanceConfirmDialog>

    <AttendanceConfirmDialog
      :model-value="pendingGenerate"
      title="Generate bills for this month?"
      confirm-label="Generate"
      confirm-color="primary"
      :loading="generating"
      @update:model-value="value => { if (!value) pendingGenerate = false }"
      @confirm="confirmGenerate"
      @cancel="pendingGenerate = false"
    >
      Replaces drafts, skips issued and paid, deletes leftover drafts, and may restore void bills if the student is still enrolled.
    </AttendanceConfirmDialog>
  </VContainer>
</template>
