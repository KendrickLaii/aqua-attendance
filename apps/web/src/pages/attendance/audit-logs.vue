<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listAuditLogsWithTotal } from '@/api/attendance/auditLogs'
import type { AuditLog } from '@/api/attendance/auditLogs'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'

definePage({ meta: {} })

const pageSize = ref(40)
const pageSizeOptions = [10, 20, 40, 60, 100]

const authStore = useAttendanceAuthStore()
const router = useRouter()

const logs = ref<AuditLog[]>([])
const totalCount = ref(0)
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')

useAutoClearAlerts(loadError)

const filterAction = ref('')
const filterTable = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const searchQuery = ref('')
const page = ref(1)
const detailDialog = ref(false)
const selectedLog = ref<AuditLog | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

const actionOptions = [
  { title: 'All', value: '' },
  { title: 'Create', value: 'CREATE' },
  { title: 'Update', value: 'UPDATE' },
  { title: 'Delete', value: 'DELETE' },
  { title: 'Export', value: 'DATA_EXPORT' },
  { title: 'Manual Correction', value: 'MANUAL_CORRECTION' },
]

const tableOptions = [
  { title: 'Attendance Events', value: 'attendance_events' },
  { title: 'Attendance Summaries', value: 'attendance_summaries' },
  { title: 'Payroll Records', value: 'payroll_records' },
  { title: 'Tuition Invoices', value: 'tuition_invoices' },
  { title: 'Tuition Receipts', value: 'tuition_receipts' },
  { title: 'Units', value: 'units' },
  { title: 'Users', value: 'users' },
]

const visibleLogs = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query)
    return logs.value

  return logs.value.filter(log => {
    const haystack = [
      log.action,
      log.table_name,
      log.description,
      log.username,
      log.user_full_name,
      log.ip_address,
      log.record_id,
      log.session_id,
      log.user_id,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()

    return haystack.includes(query)
  })
})

const activeFilterCount = computed(() => {
  let count = 0
  if (filterAction.value)
    count++
  if (filterTable.value)
    count++
  if (dateFrom.value)
    count++
  if (dateTo.value)
    count++
  if (searchQuery.value.trim())
    count++

  return count
})

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading audit logs…'

  const total = totalCount.value
  if (total === 0)
    return 'No audit logs found'

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
      page_size: pageSize.value,
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

function resetFilters() {
  filterAction.value = ''
  filterTable.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  searchQuery.value = ''
  loadLogs(true, true)
}

function setActionFilter(value: string) {
  filterAction.value = value
  loadLogs(true, true)
}

watch([filterTable, dateFrom, dateTo], () => {
  loadLogs(true, true)
})

function onPageSizeChange() {
  page.value = 1
  loadLogs(true)
}

function actionColor(action: string) {
  if (action === 'CREATE')
    return 'success'
  if (action === 'UPDATE' || action === 'MANUAL_CORRECTION')
    return 'warning'
  if (action === 'DELETE')
    return 'error'
  if (action === 'DATA_EXPORT')
    return 'info'

  return 'grey'
}

function actionIcon(action: string) {
  if (action === 'CREATE')
    return 'ri-add-circle-line'
  if (action === 'UPDATE')
    return 'ri-edit-circle-line'
  if (action === 'MANUAL_CORRECTION')
    return 'ri-history-line'
  if (action === 'DELETE')
    return 'ri-delete-bin-6-line'
  if (action === 'DATA_EXPORT')
    return 'ri-download-cloud-2-line'

  return 'ri-shield-keyhole-line'
}

function formatTimestamp(iso: string) {
  return iso?.slice(0, 16).replace('T', ' ') ?? '—'
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
  <VContainer class="audit-logs-page">
    <VFadeTransition>
      <div>
        <!-- Header -->
        <VRow
          class="page-header mb-4"
          align="end"
        >
          <VCol
            cols="12"
            lg="5"
          >
            <div class="d-flex align-center gap-3 mb-1">
              <div class="page-icon">
                <VIcon
                  size="22"
                  color="primary"
                >
                  ri-shield-check-line
                </VIcon>
              </div>
              <h1 class="text-h5 font-weight-bold">
                Audit Logs
              </h1>
            </div>
            <p class="text-subtitle-2 text-medium-emphasis ms-12">
              {{ pageSubtitle }}
            </p>
          </VCol>
        </VRow>

        <!-- Filter toolbar -->
        <VCard
          class="filter-card mb-4"
          variant="outlined"
        >
          <VCardText class="pa-4">
            <div class="filter-grid">
              <!-- Keyword search -->
              <VTextField
                v-model="searchQuery"
                label="Search logs"
                placeholder="Action, table, user, IP…"
                prepend-inner-icon="ri-search-line"
                density="comfortable"
                hide-details
                clearable
                variant="outlined"
                class="filter-search"
              />

              <!-- Date range -->
              <div class="date-range">
                <VTextField
                  v-model="dateFrom"
                  label="From"
                  type="date"
                  density="comfortable"
                  hide-details
                  variant="outlined"
                  prepend-inner-icon="ri-calendar-line"
                  class="date-field"
                />
                <span class="date-separator text-caption text-medium-emphasis">to</span>
                <VTextField
                  v-model="dateTo"
                  label="To"
                  type="date"
                  density="comfortable"
                  hide-details
                  variant="outlined"
                  prepend-inner-icon="ri-calendar-line"
                  class="date-field"
                />
              </div>

              <!-- Table autocomplete -->
              <VAutocomplete
                v-model="filterTable"
                :items="tableOptions"
                label="Table"
                placeholder="All tables"
                item-title="title"
                item-value="value"
                density="comfortable"
                hide-details
                clearable
                variant="outlined"
                prepend-inner-icon="ri-database-2-line"
                class="filter-table"
              />

              <!-- Refresh & reset -->
              <div class="filter-actions">
                <VBtn
                  v-if="activeFilterCount > 0"
                  variant="text"
                  color="secondary"
                  size="small"
                  prepend-icon="ri-filter-off-line"
                  @click="resetFilters"
                >
                  Clear {{ activeFilterCount }}
                </VBtn>
                <VBtn
                  :loading="refreshing"
                  variant="tonal"
                  color="primary"
                  size="small"
                  prepend-icon="ri-refresh-line"
                  @click="loadLogs(true)"
                >
                  Refresh
                </VBtn>
              </div>
            </div>

            <!-- Action chips -->
            <div class="action-chips mt-4">
              <span class="text-caption text-medium-emphasis me-2 action-label">Action:</span>
              <VChip
                v-for="opt in actionOptions"
                :key="opt.value || 'all'"
                :variant="filterAction === opt.value ? 'flat' : 'tonal'"
                :color="filterAction === opt.value ? 'primary' : 'default'"
                size="small"
                :prepend-icon="filterAction === opt.value ? 'ri-check-line' : undefined"
                :aria-pressed="filterAction === opt.value"
                class="action-chip"
                @click="setActionFilter(opt.value)"
              >
                {{ opt.title }}
              </VChip>
            </div>
          </VCardText>
        </VCard>

        <!-- Loading / error -->
        <VProgressLinear
          v-if="loading && !refreshing"
          indeterminate
          color="primary"
          class="mb-2 rounded"
          rounded
        />

        <VAlert
          v-if="loadError"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
          closable
          @click:close="loadError = ''"
        >
          {{ loadError }}
        </VAlert>

        <!-- Table -->
        <VCard
          class="table-card"
          variant="outlined"
        >
          <div class="audit-table-scroll">
            <VTable
              class="audit-table"
              density="comfortable"
              hover
            >
              <thead>
                <tr>
                  <th class="col-time">
                    Time
                  </th>
                  <th class="col-action">
                    Action
                  </th>
                  <th class="col-table">
                    Table
                  </th>
                  <th class="col-desc">
                    Description
                  </th>
                  <th class="col-user">
                    User
                  </th>
                  <th class="col-ip">
                    IP
                  </th>
                  <th class="col-more" />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="log in visibleLogs"
                  :key="log.id"
                  class="audit-row"
                  @click="openDetailDialog(log)"
                >
                  <td class="col-time">
                    <div class="text-body-2">
                      {{ formatTimestamp(log.created_at).split(' ')[0] }}
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      {{ formatTimestamp(log.created_at).split(' ')[1] }}
                    </div>
                  </td>
                  <td class="col-action">
                    <VChip
                      :color="actionColor(log.action)"
                      :prepend-icon="actionIcon(log.action)"
                      size="small"
                      label
                    >
                      {{ log.action }}
                    </VChip>
                  </td>
                  <td class="col-table text-body-2 font-mono">
                    {{ log.table_name }}
                  </td>
                  <td class="col-desc">
                    <span
                      v-if="log.description"
                      class="text-body-2"
                    >{{ log.description }}</span>
                    <span
                      v-else
                      class="text-medium-emphasis"
                    >—</span>
                  </td>
                  <td class="col-user">
                    <template v-if="log.username || log.user_full_name">
                      <div class="d-flex align-center gap-2">
                        <VAvatar
                          color="primary"
                          size="24"
                          class="text-caption"
                        >
                          {{ (log.user_full_name || log.username || '?').charAt(0).toUpperCase() }}
                        </VAvatar>
                        <div>
                          <div class="text-body-2">
                            {{ log.user_full_name || log.username }}
                          </div>
                          <div
                            v-if="log.username && log.user_full_name"
                            class="text-caption text-medium-emphasis"
                          >
                            @{{ log.username }}
                          </div>
                        </div>
                      </div>
                    </template>
                    <span
                      v-else
                      class="text-medium-emphasis"
                    >—</span>
                  </td>
                  <td class="col-ip text-caption font-mono">
                    {{ log.ip_address || '—' }}
                  </td>
                  <td class="col-more">
                    <VBtn
                      icon
                      size="x-small"
                      variant="text"
                      color="primary"
                      title="View details"
                      @click.stop="openDetailDialog(log)"
                    >
                      <VIcon>ri-eye-line</VIcon>
                    </VBtn>
                  </td>
                </tr>
                <tr v-if="visibleLogs.length === 0 && !loading">
                  <td
                    colspan="7"
                    class="empty-state"
                  >
                    <VIcon
                      size="48"
                      class="mb-3"
                      color="secondary"
                    >
                      ri-shield-keyhole-line
                    </VIcon>
                    <div class="text-h6">
                      No audit logs found
                    </div>
                    <p class="text-body-2 text-medium-emphasis mb-0">
                      Try adjusting your filters or refresh the page.
                    </p>
                  </td>
                </tr>
              </tbody>
            </VTable>
          </div>

          <!-- Pagination footer -->
          <VDivider />
          <div class="d-flex align-center justify-space-between pa-3">
            <div class="d-flex align-center gap-2">
              <span class="text-caption text-medium-emphasis">{{ totalCount }} total</span>
              <VSelect
                v-model="pageSize"
                :items="pageSizeOptions"
                density="compact"
                variant="plain"
                hide-details
                style="max-width: 70px;"
                @update:model-value="onPageSizeChange"
              />
              <span class="text-caption text-medium-emphasis">per page</span>
            </div>
            <VPagination
              v-model="page"
              :length="totalPages"
              :total-visible="5"
              density="comfortable"
              size="small"
              @update:model-value="loadLogs(true)"
            />
          </div>
        </VCard>

        <!-- Detail dialog -->
        <VDialog
          v-model="detailDialog"
          max-width="620"
          scrollable
        >
          <VCard v-if="selectedLog">
            <VCardTitle class="pa-4 d-flex align-center justify-space-between">
              <div class="d-flex align-center gap-2">
                <VIcon color="primary">
                  ri-shield-check-line
                </VIcon>
                <span class="text-h6">Audit Log Detail</span>
              </div>
              <VBtn
                icon
                variant="text"
                size="small"
                @click="closeDetailDialog"
              >
                <VIcon>ri-close-line</VIcon>
              </VBtn>
            </VCardTitle>

            <VDivider />

            <VCardText class="pa-4">
              <div class="detail-section">
                <VChip
                  :color="actionColor(selectedLog.action)"
                  :prepend-icon="actionIcon(selectedLog.action)"
                  size="small"
                  label
                  class="mb-2"
                >
                  {{ selectedLog.action }}
                </VChip>
                <div class="text-h6">
                  {{ selectedLog.table_name }}
                </div>
                <p class="text-body-2 text-medium-emphasis mb-0">
                  {{ selectedLog.description || 'No description provided.' }}
                </p>
              </div>

              <VRow class="meta-grid">
                <VCol
                  cols="6"
                  sm="4"
                >
                  <div class="text-caption text-medium-emphasis">
                    Timestamp
                  </div>
                  <div class="text-body-2">
                    {{ formatTimestamp(selectedLog.created_at) }}
                  </div>
                </VCol>
                <VCol
                  cols="6"
                  sm="4"
                >
                  <div class="text-caption text-medium-emphasis">
                    Record ID
                  </div>
                  <div class="text-body-2 font-mono text-truncate">
                    {{ selectedLog.record_id || '—' }}
                  </div>
                </VCol>
                <VCol
                  cols="6"
                  sm="4"
                >
                  <div class="text-caption text-medium-emphasis">
                    Session
                  </div>
                  <div class="text-body-2 font-mono text-truncate">
                    {{ selectedLog.session_id || '—' }}
                  </div>
                </VCol>
                <VCol
                  cols="6"
                  sm="4"
                >
                  <div class="text-caption text-medium-emphasis">
                    User
                  </div>
                  <div class="text-body-2 text-truncate">
                    {{ selectedLog.user_full_name || selectedLog.username || selectedLog.user_id || '—' }}
                  </div>
                </VCol>
                <VCol
                  cols="6"
                  sm="4"
                >
                  <div class="text-caption text-medium-emphasis">
                    IP Address
                  </div>
                  <div class="text-body-2 font-mono text-truncate">
                    {{ selectedLog.ip_address || '—' }}
                  </div>
                </VCol>
                <VCol
                  cols="6"
                  sm="4"
                >
                  <div class="text-caption text-medium-emphasis">
                    Batch
                  </div>
                  <div class="text-body-2">
                    {{ selectedLog.batch_operation ? 'Yes' : 'No' }}
                  </div>
                </VCol>
              </VRow>

              <VExpansionPanels
                v-if="selectedLog.old_values || selectedLog.new_values"
                multiple
                flat
                class="detail-panels"
              >
                <VExpansionPanel v-if="selectedLog.old_values">
                  <VExpansionPanelTitle class="text-body-2 font-weight-medium">
                    <VIcon
                      size="18"
                      class="me-2"
                    >
                      ri-arrow-go-back-line
                    </VIcon>
                    Old Values
                  </VExpansionPanelTitle>
                  <VExpansionPanelText>
                    <pre class="json-block">{{ JSON.stringify(selectedLog.old_values, null, 2) }}</pre>
                  </VExpansionPanelText>
                </VExpansionPanel>

                <VExpansionPanel v-if="selectedLog.new_values">
                  <VExpansionPanelTitle class="text-body-2 font-weight-medium">
                    <VIcon
                      size="18"
                      class="me-2"
                    >
                      ri-arrow-go-forward-line
                    </VIcon>
                    New Values
                  </VExpansionPanelTitle>
                  <VExpansionPanelText>
                    <pre class="json-block">{{ JSON.stringify(selectedLog.new_values, null, 2) }}</pre>
                  </VExpansionPanelText>
                </VExpansionPanel>
              </VExpansionPanels>
            </VCardText>

            <VDivider />

            <VCardActions class="pa-4 justify-end">
              <VBtn
                variant="tonal"
                color="secondary"
                size="small"
                @click="closeDetailDialog"
              >
                Close
              </VBtn>
            </VCardActions>
          </VCard>
        </VDialog>
      </div>
    </VFadeTransition>
  </VContainer>
</template>

<style scoped lang="scss">
.audit-logs-page {
  --audit-radius: 12px;
  --audit-border: rgba(var(--v-border-color), var(--v-border-opacity));
}

.page-header {
  .page-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    inline-size: 40px;
    block-size: 40px;
    border-radius: 10px;
    background: rgba(var(--v-theme-primary), 0.08);
  }
}

.filter-card {
  border-radius: var(--audit-radius);

  :deep(.v-card__underlay) {
    display: none;
  }
}

.filter-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;

  @media (width >= 600px) {
    grid-template-columns: 1fr 1fr;
  }

  @media (width >= 960px) {
    grid-template-columns: 1.25fr auto auto auto;
  }
}

.filter-search {
  min-inline-size: 220px;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 12px;
  min-inline-size: 280px;
}

.date-field {
  min-inline-size: 140px;
}

.date-separator {
  white-space: nowrap;
}

.filter-table {
  min-inline-size: 180px;
}

.filter-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-inline-size: 180px;
}

.action-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;

  .action-label {
    line-height: 32px;
  }

  .action-chip {
    cursor: pointer;
    transition: transform 0.15s ease;

    &:hover {
      transform: translateY(-1px);
    }
  }
}

.table-card {
  border-radius: var(--audit-radius);
  overflow: hidden;
}

.audit-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.audit-table {
  min-inline-size: 900px;

  :deep(th) {
    background: rgb(var(--v-table-header-color));
    color: rgba(var(--v-theme-on-surface), var(--v-high-emphasis-opacity));
    font-weight: 600;
    font-size: 0.75rem;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    white-space: nowrap;
  }

  :deep(td),
  :deep(th) {
    padding-inline: 16px;
    padding-block: 12px;
  }

  :deep(.col-time) {
    inline-size: 120px;
    white-space: nowrap;
  }

  :deep(.col-action) {
    inline-size: 130px;
    white-space: nowrap;
  }

  :deep(.col-table) {
    inline-size: 180px;
  }

  :deep(.col-desc) {
    min-inline-size: 240px;
    max-inline-size: 420px;
  }

  :deep(.col-user) {
    min-inline-size: 180px;
  }

  :deep(.col-ip) {
    inline-size: 120px;
    white-space: nowrap;
  }

  :deep(.col-more) {
    inline-size: 56px;
    white-space: nowrap;
    text-align: end;
  }

  .audit-row {
    cursor: pointer;
    transition: background-color 0.15s ease;

    &:hover {
      background-color: rgba(var(--v-theme-primary), 0.03);
    }
  }

  .empty-state {
    text-align: center;
    padding-block: 56px;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  }
}

.detail-section {
  padding: 16px;
  margin-block-end: 20px;
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), 0.04);
}

.meta-grid {
  margin-block-end: 20px;
}

.detail-panels {
  :deep(.v-expansion-panel) {
    border: 1px solid var(--audit-border);
    border-radius: 10px !important;
    margin-block-end: 12px;
    overflow: hidden;

    &:last-child {
      margin-block-end: 0;
    }
  }
}

.json-block {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  font-family: 'Fira Code', 'Cascadia Code', 'SF Mono', Consolas, monospace;
  font-size: 0.75rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.font-mono {
  font-family: 'Fira Code', 'Cascadia Code', 'SF Mono', Consolas, monospace;
}
</style>
