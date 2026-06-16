<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listAuditLogsWithTotal } from '@/api/attendance/auditLogs'
import type { AuditLog } from '@/api/attendance/auditLogs'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: {} })

const LOG_PAGE_SIZE = 50

const authStore = useAttendanceAuthStore()
const router = useRouter()

const logs = ref<AuditLog[]>([])
const totalCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

const filterAction = ref('')
const filterTable = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const page = ref(1)
const detailDialog = ref(false)
const selectedLog = ref<AuditLog | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / LOG_PAGE_SIZE)))
const hasNextPage = computed(() => page.value < totalPages.value)
const hasPrevPage = computed(() => page.value > 1)

const actionOptions = [
  { title: 'All actions', value: '' },
  { title: 'CREATE', value: 'CREATE' },
  { title: 'UPDATE', value: 'UPDATE' },
  { title: 'DELETE', value: 'DELETE' },
  { title: 'DATA_EXPORT', value: 'DATA_EXPORT' },
]

const tableOptions = [
  { title: 'All tables', value: '' },
  { title: 'products', value: 'products' },
  { title: 'users', value: 'users' },
  { title: 'attendance_events', value: 'attendance_events' },
  { title: 'attendance_summaries', value: 'attendance_summaries' },
  { title: 'payroll_records', value: 'payroll_records' },
  { title: 'notifications', value: 'notifications' },
]

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = totalCount.value
  let label = `${total} log${total === 1 ? '' : 's'}`
  if (totalPages.value > 1)
    label += ` · page ${page.value} of ${totalPages.value}`

  return label
})

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (!authStore.isSuperAdmin) {
    router.replace({ name: 'attendance-dashboard' })

    return
  }
  await loadLogs()
})

async function loadLogs(isRefresh = false, resetPage = false) {
  if (resetPage)
    page.value = 1
  if (isRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    const result = await listAuditLogsWithTotal({
      action: filterAction.value || undefined,
      table_name: filterTable.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      page: page.value,
      page_size: LOG_PAGE_SIZE,
    })

    logs.value = result.items
    totalCount.value = result.total
  }
  catch (e) {
    console.error('Failed to load audit logs', e)
    loadError.value = formatApiError(e, 'Failed to load audit logs.')
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

watch([filterAction, filterTable, dateFrom, dateTo], () => {
  loadLogs(true, true)
})

function goToPrevPage() {
  if (page.value <= 1)
    return
  page.value -= 1
  loadLogs(true)
}

function goToNextPage() {
  if (!hasNextPage.value)
    return
  page.value += 1
  loadLogs(true)
}

function actionColor(action: string) {
  if (action === 'CREATE')
    return 'success'
  if (action === 'UPDATE')
    return 'warning'
  if (action === 'DELETE')
    return 'error'

  return 'grey'
}

function openDetailDialog(log: AuditLog) {
  selectedLog.value = log
  detailDialog.value = true
}

function closeDetailDialog() {
  detailDialog.value = false
  selectedLog.value = null
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
          Audit Logs
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
          v-model="filterAction"
          :items="actionOptions"
          item-title="title"
          item-value="value"
          label="Action"
          density="compact"
          hide-details
          class="filter-field"
        />
        <VSelect
          v-model="filterTable"
          :items="tableOptions"
          item-title="title"
          item-value="value"
          label="Table"
          density="compact"
          hide-details
          class="filter-field"
        />
        <VTextField
          v-model="dateFrom"
          label="From"
          type="date"
          density="compact"
          hide-details
          class="date-field"
        />
        <VTextField
          v-model="dateTo"
          label="To"
          type="date"
          density="compact"
          hide-details
          class="date-field"
        />
        <VBtn
          icon
          variant="text"
          :loading="refreshing"
          @click="loadLogs(true)"
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

    <div class="audit-table-scroll">
      <VTable
        class="audit-table"
        density="compact"
        hover
      >
        <thead>
          <tr>
            <th>Time</th>
            <th>Action</th>
            <th>Table</th>
            <th>Description</th>
            <th>User</th>
            <th>IP</th>
            <th class="col-action" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="log in logs"
            :key="log.id"
          >
            <td class="text-caption">
              {{ log.created_at.slice(0, 16).replace('T', ' ') }}
            </td>
            <td>
              <VChip
                :color="actionColor(log.action)"
                size="small"
                label
              >
                {{ log.action }}
              </VChip>
            </td>
            <td>{{ log.table_name }}</td>
            <td>
              <span
                v-if="log.description"
                class="text-caption"
              >{{ log.description }}</span>
              <span
                v-else
                class="text-medium-emphasis"
              >—</span>
            </td>
            <td>
              <template v-if="log.username || log.user_full_name">
                <div class="text-body-2">
                  {{ log.user_full_name || log.username }}
                </div>
                <div
                  v-if="log.username && log.user_full_name"
                  class="text-caption text-medium-emphasis"
                >
                  @{{ log.username }}
                </div>
              </template>
              <span
                v-else
                class="text-medium-emphasis"
              >—</span>
            </td>
            <td class="text-caption">
              {{ log.ip_address || '—' }}
            </td>
            <td class="col-action">
              <VBtn
                icon
                size="x-small"
                variant="text"
                title="View details"
                @click="openDetailDialog(log)"
              >
                <VIcon>tabler-eye</VIcon>
              </VBtn>
            </td>
          </tr>
          <tr v-if="logs.length === 0 && !loading">
            <td
              colspan="7"
              class="text-center text-medium-emphasis py-6"
            >
              No audit logs found.
            </td>
          </tr>
        </tbody>
      </VTable>
    </div>

    <div class="d-flex align-center justify-space-between mt-3">
      <span class="text-caption text-medium-emphasis">{{ totalCount }} total</span>
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
      v-model="detailDialog"
      max-width="560"
    >
      <VCard v-if="selectedLog">
        <VCardTitle class="text-h6 d-flex align-center justify-space-between">
          <span>Audit Log Detail</span>
          <VBtn
            icon
            variant="text"
            size="small"
            @click="closeDetailDialog"
          >
            <VIcon>tabler-x</VIcon>
          </VBtn>
        </VCardTitle>
        <VCardText>
          <div class="mb-3">
            <div class="text-caption text-medium-emphasis">
              Action
            </div>
            <VChip
              :color="actionColor(selectedLog.action)"
              size="small"
              label
            >
              {{ selectedLog.action }}
            </VChip>
            <span class="text-body-2 ms-2">{{ selectedLog.table_name }}</span>
          </div>
          <div class="mb-3">
            <div class="text-caption text-medium-emphasis">
              Description
            </div>
            <div class="text-body-2">
              {{ selectedLog.description || '—' }}
            </div>
          </div>
          <div class="mb-3">
            <div class="text-caption text-medium-emphasis">
              Record ID
            </div>
            <div class="text-body-2 font-mono">
              {{ selectedLog.record_id || '—' }}
            </div>
          </div>
          <VRow v-if="selectedLog.old_values">
            <VCol cols="12">
              <div class="text-caption text-medium-emphasis mb-1">
                Old Values
              </div>
              <VCard
                variant="outlined"
                class="pa-2"
              >
                <pre class="text-caption" style="margin: 0; white-space: pre-wrap; word-break: break-word;">{{ JSON.stringify(selectedLog.old_values, null, 2) }}</pre>
              </VCard>
            </VCol>
          </VRow>
          <VRow v-if="selectedLog.new_values">
            <VCol cols="12">
              <div class="text-caption text-medium-emphasis mb-1">
                New Values
              </div>
              <VCard
                variant="outlined"
                class="pa-2"
              >
                <pre class="text-caption" style="margin: 0; white-space: pre-wrap; word-break: break-word;">{{ JSON.stringify(selectedLog.new_values, null, 2) }}</pre>
              </VCard>
            </VCol>
          </VRow>
          <VRow>
            <VCol
              cols="6"
              sm="4"
            >
              <div class="text-caption text-medium-emphasis">
                User
              </div>
              <div class="text-body-2">
                {{ selectedLog.user_full_name || selectedLog.username || selectedLog.user_id || '—' }}
              </div>
            </VCol>
            <VCol
              cols="6"
              sm="4"
            >
              <div class="text-caption text-medium-emphasis">
                IP
              </div>
              <div class="text-body-2">
                {{ selectedLog.ip_address || '—' }}
              </div>
            </VCol>
            <VCol
              cols="6"
              sm="4"
            >
              <div class="text-caption text-medium-emphasis">
                Session
              </div>
              <div class="text-body-2">
                {{ selectedLog.session_id || '—' }}
              </div>
            </VCol>
          </VRow>
        </VCardText>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.filter-field {
  inline-size: 140px;
}

.date-field {
  inline-size: 140px;
}

.audit-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.audit-table :deep(th),
.audit-table :deep(td) {
  white-space: nowrap;
}

.audit-table :deep(.col-action) {
  width: 1%;
  white-space: nowrap;
}

.font-mono {
  font-family: monospace;
}
</style>
