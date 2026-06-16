<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listPayrollRecordsWithTotal, updatePayrollRecord, deletePayrollRecord } from '@/api/attendance/payroll'
import type { PayrollRecord } from '@/api/attendance/payroll'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const PAYROLL_PAGE_SIZE = 50

const authStore = useAttendanceAuthStore()
const router = useRouter()

const records = ref<PayrollRecord[]>([])
const totalCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filterStatus = ref('')
const page = ref(1)
const deleteDialog = ref(false)
const deleteTarget = ref<PayrollRecord | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / PAYROLL_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)

const statusOptions = [
  { title: 'All statuses', value: '' },
  { title: 'Draft', value: 'draft' },
  { title: 'Calculated', value: 'calculated' },
  { title: 'Approved', value: 'approved' },
  { title: 'Paid', value: 'paid' },
  { title: 'Cancelled', value: 'cancelled' },
]

const statusColorMap: Record<string, string> = {
  draft: 'grey',
  calculated: 'info',
  approved: 'success',
  paid: 'primary',
  cancelled: 'error',
}

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} record${total === 1 ? '' : 's'}`
  if (filterStatus.value)
    label += ` · ${filterStatus.value}`
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

const listCaption = computed(() => {
  if (loading.value || totalCount.value === 0)
    return ''

  const from = (page.value - 1) * PAYROLL_PAGE_SIZE + 1
  const to = from + records.value.length - 1

  if (totalCount.value <= PAYROLL_PAGE_SIZE)
    return `${totalCount.value} record${totalCount.value === 1 ? '' : 's'}`

  return `${from}–${to} of ${totalCount.value}`
})

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (!authStore.isAdmin) {
    router.replace({ name: 'attendance-dashboard' })

    return
  }
  await loadRecords()
})

async function loadRecords(isRefresh = false, resetPage = false) {
  if (resetPage)
    page.value = 1
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listPayrollRecordsWithTotal({
      status: filterStatus.value || undefined,
      page: page.value,
      page_size: PAYROLL_PAGE_SIZE,
    })

    records.value = result.items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load payroll records', e)
    loadError.value = formatApiError(e, 'Failed to load payroll records. Please try again.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

watch(filterStatus, () => {
  loadRecords(true, true)
})

async function updateStatus(record: PayrollRecord, newStatus: string) {
  try {
    await updatePayrollRecord(record.id, { status: newStatus })
    record.status = newStatus as PayrollRecord['status']
  }
  catch (e) {
    console.error('Failed to update status', e)
    loadError.value = formatApiError(e, 'Could not update status')
  }
}

function openDeleteDialog(record: PayrollRecord) {
  deleteTarget.value = record
  deleteDialog.value = true
}

function closeDeleteDialog() {
  deleteDialog.value = false
  deleteTarget.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value)
    return
  try {
    await deletePayrollRecord(deleteTarget.value.id)
    closeDeleteDialog()
    await loadRecords(true)
  }
  catch (e) {
    console.error('Failed to delete record', e)
    loadError.value = formatApiError(e, 'Could not delete record')
  }
}

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadRecords(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
  loadRecords(true)
}

function formatCurrency(n: number) {
  return Number.isFinite(n) ? n.toFixed(2) : '-'
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <h1 class="text-h5 font-weight-bold">
          Payroll Records
        </h1>
        <p class="text-subtitle-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </p>
      </VCol>
      <VCol
        cols="auto"
        class="d-flex flex-wrap gap-2"
      >
        <VSelect
          v-model="filterStatus"
          :items="statusOptions"
          item-title="title"
          item-value="value"
          label="Status"
          density="compact"
          hide-details
          class="status-field"
        />
        <VBtn
          icon
          variant="text"
          :loading="refreshing"
          @click="loadRecords(true)"
        >
          <VIcon>tabler-refresh</VIcon>
        </VBtn>
      </VCol>
    </VRow>

    <VProgressLinear
      v-if="loading && !refreshing"
      indeterminate
      color="primary"
      class="mb-2"
    />

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      density="compact"
      class="mb-3"
    >
      {{ loadError }}
    </VAlert>

    <div class="payroll-table-scroll">
      <VTable
        class="payroll-table"
        density="compact"
        hover
      >
        <thead>
          <tr>
            <th>Product</th>
            <th>Period</th>
            <th>Regular</th>
            <th>OT</th>
            <th class="text-end">Base</th>
            <th class="text-end">OT Pay</th>
            <th class="text-end">Gross</th>
            <th class="text-end">Net</th>
            <th>Status</th>
            <th class="col-actions" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in records"
            :key="r.id"
          >
            <td>
              <div class="font-weight-medium">
                {{ r.product_name || '—' }}
              </div>
              <div
                v-if="r.product_code"
                class="text-caption text-medium-emphasis"
              >
                {{ r.product_code }}
              </div>
            </td>
            <td>
              <div class="text-caption">
                {{ r.payroll_period_start }} – {{ r.payroll_period_end }}
              </div>
            </td>
            <td>{{ r.total_regular_hours.toFixed(1) }}h</td>
            <td>{{ r.total_overtime_hours.toFixed(1) }}h</td>
            <td class="text-end">
              {{ formatCurrency(r.base_salary) }}
            </td>
            <td class="text-end">
              {{ formatCurrency(r.overtime_pay) }}
            </td>
            <td class="text-end">
              {{ formatCurrency(r.gross_pay) }}
            </td>
            <td class="text-end">
              {{ formatCurrency(r.net_pay) }}
            </td>
            <td>
              <VChip
                :color="statusColorMap[r.status] ?? 'grey'"
                size="small"
                label
              >
                {{ r.status }}
              </VChip>
            </td>
            <td class="col-actions">
              <div class="d-flex flex-nowrap align-center">
                <VBtn
                  v-if="r.status === 'draft' || r.status === 'calculated'"
                  size="small"
                  variant="text"
                  color="success"
                  @click="updateStatus(r, 'approved')"
                >
                  Approve
                </VBtn>
                <VBtn
                  v-if="r.status === 'approved'"
                  size="small"
                  variant="text"
                  color="primary"
                  @click="updateStatus(r, 'paid')"
                >
                  Pay
                </VBtn>
                <VBtn
                  v-if="authStore.isSuperAdmin"
                  icon
                  size="small"
                  variant="text"
                  color="error"
                  @click="openDeleteDialog(r)"
                >
                  <VIcon>tabler-trash</VIcon>
                </VBtn>
              </div>
            </td>
          </tr>
          <tr v-if="records.length === 0 && !loading">
            <td
              colspan="10"
              class="text-center text-medium-emphasis py-6"
            >
              No payroll records found.
            </td>
          </tr>
        </tbody>
      </VTable>
    </div>

    <div class="d-flex align-center justify-space-between mt-3">
      <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
      <div class="d-flex align-center gap-2">
        <VBtn
          size="small"
          variant="text"
          :disabled="!hasPrevPage"
          @click="goToPrevPage"
        >
          <VIcon>tabler-chevron-left</VIcon>
        </VBtn>
        <span class="text-caption">{{ page }} / {{ totalPages }}</span>
        <VBtn
          size="small"
          variant="text"
          :disabled="!hasNextPage"
          @click="goToNextPage"
        >
          <VIcon>tabler-chevron-right</VIcon>
        </VBtn>
      </div>
    </div>
    <VDialog
      v-model="deleteDialog"
      max-width="400"
    >
      <VCard v-if="deleteTarget">
        <VCardTitle class="text-h6">
          Confirm Delete
        </VCardTitle>
        <VCardText>
          Delete payroll record for <strong>{{ deleteTarget.product_name || deleteTarget.product_code || deleteTarget.product_id }}</strong> ({{ deleteTarget.payroll_period_start }} – {{ deleteTarget.payroll_period_end }})?
        </VCardText>
        <VCardActions class="justify-end">
          <VBtn
            variant="text"
            @click="closeDeleteDialog"
          >
            Cancel
          </VBtn>
          <VBtn
            color="error"
            variant="flat"
            @click="confirmDelete"
          >
            Delete
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.status-field {
  inline-size: 160px;
}

.payroll-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.payroll-table :deep(th),
.payroll-table :deep(td) {
  white-space: nowrap;
}

.payroll-table :deep(.col-actions) {
  width: 1%;
  white-space: nowrap;
  vertical-align: middle;
}
</style>
