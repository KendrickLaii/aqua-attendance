<script setup lang="ts">
import { useDisplay } from 'vuetify'
import { type LocationItem, listLocations } from '@/api/attendance/locations'
import {
  type InventoryWarehouse,
  type InventoryWarehousePayload,
  createWarehouse,
  deleteWarehouse,
  listWarehousesWithTotal,
  updateWarehouse,
} from '@/api/attendance/inventory'
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import InventoryEmptyState from '@/components/attendance/inventory/InventoryEmptyState.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useConfirmAction } from '@/composables/useConfirmAction'
import { useLatestRequest } from '@/composables/useLatestRequest'

definePage({ meta: {} })

const display = useDisplay()
const { ensureAccess } = useAttendanceAdminGate()
const toast = useToast()
const confirm = useConfirmAction()

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const saveError = ref('')

useAutoClearAlerts(loadError)

const warehouses = ref<InventoryWarehouse[]>([])
const centres = ref<LocationItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const showInactive = ref(false)
const listReq = useLatestRequest()

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const centreById = computed(() => new Map(centres.value.map(centre => [centre.id, centre])))

const centreOptions = computed(() =>
  centres.value.map(centre => ({
    value: centre.id,
    title: [centre.name_en, centre.name_zh].filter(Boolean).join(' · '),
  })),
)

const dialogOpen = ref(false)
const editing = ref<InventoryWarehouse | null>(null)

const form = reactive({
  code: '',
  name_zh: '',
  name_en: '',
  address: '',
  phone: '',
  location_id: null as string | null,
  is_active: true,
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    centres.value = await listLocations({ is_active: true, page_size: 200 })
    await loadWarehouses()
  }
  finally {
    loading.value = false
  }
})

async function loadWarehouses() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listWarehousesWithTotal({
      search: search.value || undefined,
      is_active: showInactive.value ? undefined : true,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    warehouses.value = result.items
    total.value = result.total
  }
  catch (e) {
    if (!listReq.isLatest(token))
      return
    loadError.value = formatApiError(e, 'Failed to load warehouses.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadWarehouses()
}

function resetForm(warehouse: InventoryWarehouse | null) {
  editing.value = warehouse
  Object.assign(form, {
    code: warehouse?.code ?? '',
    name_zh: warehouse?.name_zh ?? '',
    name_en: warehouse?.name_en ?? '',
    address: warehouse?.address ?? '',
    phone: warehouse?.phone ?? '',
    location_id: warehouse?.location_id ?? null,
    is_active: warehouse?.is_active ?? true,
  })
}

function openCreate() {
  saveError.value = ''
  resetForm(null)
  dialogOpen.value = true
}

function openEdit(warehouse: InventoryWarehouse) {
  saveError.value = ''
  resetForm(warehouse)
  dialogOpen.value = true
}

function payload(): InventoryWarehousePayload {
  return {
    code: form.code.trim(),
    name_zh: form.name_zh.trim(),
    name_en: form.name_en.trim() || null,
    address: form.address.trim() || null,
    phone: form.phone.trim() || null,
    location_id: form.location_id,
    is_active: form.is_active,
  }
}

function isConflict(e: unknown): boolean {
  if (!e || typeof e !== 'object')
    return false

  const rec = e as { statusCode?: unknown; status?: unknown }
  const status = typeof rec.statusCode === 'number' ? rec.statusCode : rec.status

  return status === 409
}

async function submit() {
  saveError.value = ''
  saving.value = true

  const body = payload()
  const wasEditing = !!editing.value
  try {
    if (editing.value)
      await updateWarehouse(editing.value.id, body)
    else
      await createWarehouse(body)
    toast.show(`Warehouse ${body.code} ${wasEditing ? 'updated' : 'created'}`)
    dialogOpen.value = false
    await loadWarehouses()
  }
  catch (e) {
    const message = formatApiError(e, 'Could not save warehouse.')

    saveError.value = message
    if (isConflict(e))
      toast.show(message, 'error', 6000)
  }
  finally {
    saving.value = false
  }
}

function centreLabel(id: string | null): string {
  if (!id)
    return '—'
  const centre = centreById.value.get(id)

  return centre ? [centre.name_en, centre.name_zh].filter(Boolean).join(' · ') : id
}

function askDeactivate(warehouse: InventoryWarehouse) {
  confirm.ask(
    `Deactivate ${warehouse.code}`,
    '停用後新單據唔可以再揀呢個倉庫，已有庫存同單據會保留。',
    { label: 'Deactivate', tone: 'warning', color: 'warning' },
    async () => {
      try {
        await updateWarehouse(warehouse.id, { is_active: false })
        toast.show(`Warehouse ${warehouse.code} deactivated`)
        await loadWarehouses()
      }
      catch (e) {
        toast.show(formatApiError(e, 'Could not deactivate warehouse.'), 'error', 6000)
      }
    },
  )
}

async function activate(warehouse: InventoryWarehouse) {
  try {
    await updateWarehouse(warehouse.id, { is_active: true })
    toast.show(`Warehouse ${warehouse.code} activated`)
    await loadWarehouses()
  }
  catch (e) {
    toast.show(formatApiError(e, 'Could not activate warehouse.'), 'error', 6000)
  }
}

function askDelete(warehouse: InventoryWarehouse) {
  confirm.ask(
    `Delete ${warehouse.code}`,
    '只有未使用過的倉庫可以刪除。如果已有庫存或單據，請改為停用。',
    { label: 'Delete', tone: 'danger' },
    async () => {
      try {
        await deleteWarehouse(warehouse.id)
        toast.show(`Warehouse ${warehouse.code} deleted`)
        await loadWarehouses()
      }
      catch (e) {
        toast.show(formatApiError(e, 'Could not delete warehouse.'), 'error', 6000)
      }
    },
  )
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol>
        <div class="text-h5 font-weight-medium">
          Warehouses 倉庫
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理倉庫：編號、名稱、地址同電話。編號會用喺單號，例如 PO-MK-000001。
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadWarehouses"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New warehouse
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

    <VCard>
      <VCardText class="d-flex flex-wrap gap-3 align-center">
        <VTextField
          v-model="search"
          label="Search"
          density="comfortable"
          style="max-width: 280px"
          hide-details
          clearable
          @update:model-value="onFiltersChange"
        />
        <VCheckbox
          v-model="showInactive"
          label="Show inactive"
          density="comfortable"
          hide-details
          @update:model-value="onFiltersChange"
        />
      </VCardText>
      <div class="overflow-x-auto">
        <VTable>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Centre</th>
              <th>Phone</th>
              <th>Status</th>
              <th class="text-end">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="warehouse in warehouses"
              :key="warehouse.id"
            >
              <td class="font-weight-medium">
                {{ warehouse.code }}
              </td>
              <td>
                {{ warehouse.name_zh }}<template v-if="warehouse.name_en">
                  · {{ warehouse.name_en }}
                </template>
              </td>
              <td>{{ centreLabel(warehouse.location_id) }}</td>
              <td>{{ warehouse.phone || '—' }}</td>
              <td>
                <VChip
                  :color="warehouse.is_active ? 'success' : 'secondary'"
                  size="small"
                  variant="tonal"
                >
                  {{ warehouse.is_active ? 'Active' : 'Inactive' }}
                </VChip>
              </td>
              <td class="text-end text-no-wrap">
                <VBtn
                  variant="text"
                  size="small"
                  color="primary"
                  @click="openEdit(warehouse)"
                >
                  Edit
                </VBtn>
                <VBtn
                  v-if="warehouse.is_active"
                  variant="text"
                  size="small"
                  @click="askDeactivate(warehouse)"
                >
                  Deactivate
                </VBtn>
                <VBtn
                  v-else
                  variant="text"
                  size="small"
                  @click="activate(warehouse)"
                >
                  Activate
                </VBtn>
                <VBtn
                  variant="text"
                  size="small"
                  color="error"
                  @click="askDelete(warehouse)"
                >
                  Delete
                </VBtn>
              </td>
            </tr>
            <tr v-if="warehouses.length === 0 && !loading">
              <td colspan="6">
                <InventoryEmptyState
                  icon="ri-building-2-line"
                  :text="search ? 'No warehouses match your search.' : 'No warehouses yet.'"
                  :action-label="search ? undefined : 'New warehouse'"
                  @action="openCreate"
                />
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <AttendancePaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total-pages="totalPages"
        :caption="`Page ${page} of ${totalPages} · ${total} warehouse${total === 1 ? '' : 's'}`"
        @change="loadWarehouses"
      />
    </VCard>

    <VDialog
      :model-value="dialogOpen"
      max-width="560"
      scrollable
      :fullscreen="display.xs.value"
      @update:model-value="dialogOpen = $event"
    >
      <VCard :title="editing ? `Edit ${editing.code}` : 'New warehouse'">
        <VCardText>
          <VAlert
            v-if="saveError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            {{ saveError }}
          </VAlert>
          <div class="text-overline text-medium-emphasis mb-2">
            Identification
          </div>
          <VRow>
            <VCol
              cols="12"
              sm="6"
            >
              <VTextField
                v-model="form.code"
                label="Code"
                hint="Used in document numbers, e.g. PO-MK-000001. Max 20."
                persistent-hint
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VTextField
                v-model="form.name_zh"
                label="Name (zh)"
                density="comfortable"
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="form.name_en"
                label="Name (en)"
                density="comfortable"
              />
            </VCol>
          </VRow>
          <div class="text-overline text-medium-emphasis mb-2 mt-4">
            Place
          </div>
          <VRow>
            <VCol cols="12">
              <VSelect
                v-model="form.location_id"
                :items="centreOptions"
                label="Centre 中心"
                hint="可以留空。呢個倉庫屬於邊個中心。"
                persistent-hint
                density="comfortable"
                clearable
              />
            </VCol>
            <VCol cols="12">
              <VTextField
                v-model="form.address"
                label="Address"
                density="comfortable"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
            >
              <VTextField
                v-model="form.phone"
                label="Phone"
                density="comfortable"
              />
            </VCol>
          </VRow>
          <div class="text-overline text-medium-emphasis mb-1 mt-4">
            Status
          </div>
          <VCheckbox
            v-model="form.is_active"
            label="Active"
            density="comfortable"
            hide-details
          />
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="dialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            :disabled="!form.code.trim() || !form.name_zh.trim()"
            @click="submit"
          >
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <AttendanceConfirmDialog
      v-model="confirm.open.value"
      :title="confirm.title.value"
      :confirm-label="confirm.label.value"
      :confirm-color="confirm.color.value"
      :tone="confirm.tone.value"
      :details="confirm.details.value"
      :loading="confirm.loading.value"
      @confirm="confirm.run"
    >
      {{ confirm.message.value }}
    </AttendanceConfirmDialog>
  </VContainer>
</template>
