<script setup lang="ts">
import {
  type InventorySupplier,
  type InventorySupplierPayload,
  createSupplier,
  listSuppliers,
  updateSupplier,
} from '@/api/attendance/inventoryPurchasing'
import AttendancePaginationBar from '@/components/attendance/AttendancePaginationBar.vue'
import { formatApiError } from '@/utils/formatApiDetail'
import { useAutoClearAlerts } from '@/composables/useAutoClearAlert'
import { useLatestRequest } from '@/composables/useLatestRequest'

definePage({ meta: {} })

const { ensureAccess } = useAttendanceAdminGate()

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const saveError = ref('')
const saveSuccess = ref('')

useAutoClearAlerts(loadError)
useAutoClearAlerts(saveError)
useAutoClearAlerts(saveSuccess)

const suppliers = ref<InventorySupplier[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const showInactive = ref(false)
const listReq = useLatestRequest()

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const dialogOpen = ref(false)
const editing = ref<InventorySupplier | null>(null)

const form = reactive<InventorySupplierPayload>({
  code: '',
  name_zh: '',
  name_en: '',
  contact_name: '',
  phone: '',
  email: '',
  address: '',
  payment_terms: '',
  is_active: true,
})

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    await loadSuppliers()
  }
  finally {
    loading.value = false
  }
})

async function loadSuppliers() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listSuppliers({
      search: search.value || undefined,
      is_active: showInactive.value ? undefined : true,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    suppliers.value = result.items
    total.value = result.total
  }
  catch (e) {
    if (!listReq.isLatest(token))
      return
    loadError.value = formatApiError(e, 'Failed to load suppliers.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadSuppliers()
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    code: '',
    name_zh: '',
    name_en: '',
    contact_name: '',
    phone: '',
    email: '',
    address: '',
    payment_terms: '',
    is_active: true,
  })
  dialogOpen.value = true
}

function openEdit(supplier: InventorySupplier) {
  editing.value = supplier
  Object.assign(form, {
    code: supplier.code,
    name_zh: supplier.name_zh,
    name_en: supplier.name_en,
    contact_name: supplier.contact_name,
    phone: supplier.phone,
    email: supplier.email,
    address: supplier.address,
    payment_terms: supplier.payment_terms,
    is_active: supplier.is_active,
  })
  dialogOpen.value = true
}

async function submit() {
  saveError.value = ''
  saveSuccess.value = ''
  saving.value = true
  try {
    const payload = { ...form }

    if (editing.value)
      await updateSupplier(editing.value.id, payload)
    else
      await createSupplier(payload)

    saveSuccess.value = editing.value ? 'Supplier updated.' : 'Supplier created.'
    dialogOpen.value = false
    await loadSuppliers()
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Failed to save supplier.')
  }
  finally {
    saving.value = false
  }
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
          Suppliers 供應商
        </div>
        <div class="text-body-2 text-medium-emphasis">
          這一頁管理向誰進貨（供應商資料）。
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadSuppliers"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New supplier
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
      v-if="saveSuccess"
      type="success"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="saveSuccess = ''"
    >
      {{ saveSuccess }}
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
              <th>Contact</th>
              <th>Phone</th>
              <th>Payment terms</th>
              <th>Status</th>
              <th class="text-end">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="supplier in suppliers"
              :key="supplier.id"
            >
              <td class="font-weight-medium">
                {{ supplier.code }}
              </td>
              <td>
                {{ supplier.name_zh }}<template v-if="supplier.name_en">
                  · {{ supplier.name_en }}
                </template>
              </td>
              <td>{{ supplier.contact_name || '—' }}</td>
              <td>{{ supplier.phone || '—' }}</td>
              <td>{{ supplier.payment_terms || '—' }}</td>
              <td>
                <VChip
                  :color="supplier.is_active ? 'success' : 'secondary'"
                  size="small"
                  variant="tonal"
                >
                  {{ supplier.is_active ? 'Active' : 'Inactive' }}
                </VChip>
              </td>
              <td class="text-end">
                <VBtn
                  variant="text"
                  size="small"
                  color="primary"
                  @click="openEdit(supplier)"
                >
                  Edit
                </VBtn>
              </td>
            </tr>
            <tr v-if="suppliers.length === 0 && !loading">
              <td
                colspan="7"
                class="text-center text-medium-emphasis py-8"
              >
                No suppliers yet — click "New supplier" to add one.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <AttendancePaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total-pages="totalPages"
        :caption="`Page ${page} of ${totalPages} · ${total} supplier${total === 1 ? '' : 's'}`"
        @change="loadSuppliers"
      />
    </VCard>

    <VDialog
      v-model="dialogOpen"
      max-width="560"
    >
      <VCard :title="editing ? `Edit ${editing.code}` : 'New supplier'">
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
          <VTextField
            v-model="form.code"
            label="Code"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.name_zh"
            label="Name (zh)"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.name_en"
            label="Name (en)"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.contact_name"
            label="Contact"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.phone"
            label="Phone"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.email"
            label="Email"
            type="email"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.address"
            label="Address"
            density="comfortable"
            class="mb-3"
          />
          <VTextField
            v-model="form.payment_terms"
            label="Payment terms"
            hint="e.g. NET30"
            persistent-hint
            density="comfortable"
            class="mb-3"
          />
          <VCheckbox
            v-model="form.is_active"
            label="Active"
            density="comfortable"
            hide-details
          />
        </VCardText>
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
            :disabled="!form.code || !form.name_zh"
            @click="submit"
          >
            Save
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
