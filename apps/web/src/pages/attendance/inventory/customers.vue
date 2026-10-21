<script setup lang="ts">
import {
  type InventoryCustomer,
  type InventoryCustomerPayload,
  type InventoryCustomerType,
  createCustomer,
  createCustomerFromStudent,
  listCustomers,
  updateCustomer,
} from '@/api/attendance/inventorySales'
import { type Unit, listUnits } from '@/api/attendance/units'
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

const customers = ref<InventoryCustomer[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const search = ref('')
const typeFilter = ref<InventoryCustomerType | null>(null)
const showInactive = ref(false)
const listReq = useLatestRequest()

const typeOptions = [
  { value: 'individual' as const, title: 'Individual 個人' },
  { value: 'company' as const, title: 'Company 公司' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const dialogOpen = ref(false)
const editing = ref<InventoryCustomer | null>(null)

const form = reactive<InventoryCustomerPayload>({
  code: '',
  name_zh: '',
  name_en: '',
  type: 'individual',
  contact_name: '',
  phone: '',
  email: '',
  address: '',
  is_active: true,
})

const studentDialogOpen = ref(false)
const studentUnits = ref<Unit[]>([])
const studentSearch = ref('')
const selectedStudentId = ref<string | null>(null)
const studentLoading = ref(false)

const studentOptions = computed(() =>
  studentUnits.value.map(u => ({
    value: u.id,
    title: [u.code, u.full_name].filter(Boolean).join(' · '),
  })),
)

onMounted(async () => {
  if (!(await ensureAccess()))
    return
  loading.value = true
  try {
    await loadCustomers()
  }
  finally {
    loading.value = false
  }
})

async function loadCustomers() {
  loadError.value = ''

  const token = listReq.next()
  try {
    const result = await listCustomers({
      search: search.value || undefined,
      type: typeFilter.value ?? undefined,
      is_active: showInactive.value ? undefined : true,
      page: page.value,
      page_size: pageSize.value,
    })

    if (!listReq.isLatest(token))
      return
    customers.value = result.items
    total.value = result.total
  }
  catch (e) {
    if (!listReq.isLatest(token))
      return
    loadError.value = formatApiError(e, 'Failed to load customers.')
  }
}

function onFiltersChange() {
  page.value = 1
  loadCustomers()
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    code: '',
    name_zh: '',
    name_en: '',
    type: 'individual',
    contact_name: '',
    phone: '',
    email: '',
    address: '',
    is_active: true,
  })
  dialogOpen.value = true
}

function openEdit(customer: InventoryCustomer) {
  editing.value = customer
  Object.assign(form, {
    code: customer.code,
    name_zh: customer.name_zh,
    name_en: customer.name_en,
    type: customer.type,
    contact_name: customer.contact_name,
    phone: customer.phone,
    email: customer.email,
    address: customer.address,
    is_active: customer.is_active,
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
      await updateCustomer(editing.value.id, payload)
    else
      await createCustomer(payload)

    saveSuccess.value = editing.value ? 'Customer updated.' : 'Customer created.'
    dialogOpen.value = false
    await loadCustomers()
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Failed to save customer.')
  }
  finally {
    saving.value = false
  }
}

async function openStudentPicker() {
  studentDialogOpen.value = true
  selectedStudentId.value = null
  await loadStudents()
}

async function loadStudents() {
  studentLoading.value = true
  try {
    studentUnits.value = await listUnits({
      unit_type: 'student',
      is_active: true,
      search: studentSearch.value || undefined,
      page_size: 50,
    })
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Failed to load students.')
  }
  finally {
    studentLoading.value = false
  }
}

async function submitFromStudent() {
  if (!selectedStudentId.value)
    return
  saveError.value = ''
  saveSuccess.value = ''
  saving.value = true
  try {
    const customer = await createCustomerFromStudent(selectedStudentId.value)

    saveSuccess.value = `Customer ${customer.code} created from student.`
    studentDialogOpen.value = false
    await loadCustomers()
  }
  catch (e) {
    saveError.value = formatApiError(e, 'Failed to create customer from student.')
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
          Customers 客戶
        </div>
      </VCol>
      <VCol cols="auto">
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="loading"
          @click="loadCustomers"
        >
          Refresh
        </VBtn>
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-user-received-line"
          class="ms-2"
          @click="openStudentPicker"
        >
          From student
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          class="ms-2"
          @click="openCreate"
        >
          New customer
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
        <VSelect
          v-model="typeFilter"
          :items="typeOptions"
          label="Type"
          density="comfortable"
          style="max-width: 200px"
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
              <th>Type</th>
              <th>Contact</th>
              <th>Phone</th>
              <th>Status</th>
              <th class="text-end">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="customer in customers"
              :key="customer.id"
            >
              <td class="font-weight-medium">
                {{ customer.code }}
              </td>
              <td>
                {{ customer.name_zh }}<template v-if="customer.name_en">
                  · {{ customer.name_en }}
                </template>
              </td>
              <td class="text-capitalize">
                {{ customer.type }}
              </td>
              <td>{{ customer.contact_name || '—' }}</td>
              <td>{{ customer.phone || '—' }}</td>
              <td>
                <VChip
                  :color="customer.is_active ? 'success' : 'secondary'"
                  size="small"
                  variant="tonal"
                >
                  {{ customer.is_active ? 'Active' : 'Inactive' }}
                </VChip>
              </td>
              <td class="text-end">
                <VBtn
                  variant="text"
                  size="small"
                  color="primary"
                  @click="openEdit(customer)"
                >
                  Edit
                </VBtn>
              </td>
            </tr>
            <tr v-if="customers.length === 0 && !loading">
              <td
                colspan="7"
                class="text-center text-medium-emphasis py-8"
              >
                No customers yet — click "New customer" or "From student" to add one.
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
      <AttendancePaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total-pages="totalPages"
        :caption="`Page ${page} of ${totalPages} · ${total} customer${total === 1 ? '' : 's'}`"
        @change="loadCustomers"
      />
    </VCard>

    <VDialog
      v-model="dialogOpen"
      max-width="560"
    >
      <VCard :title="editing ? `Edit ${editing.code}` : 'New customer'">
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
          <VSelect
            v-model="form.type"
            :items="typeOptions"
            label="Type"
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

    <VDialog
      v-model="studentDialogOpen"
      max-width="520"
    >
      <VCard title="Create customer from student">
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
            v-model="studentSearch"
            label="Search students"
            density="comfortable"
            class="mb-3"
            clearable
            @update:model-value="loadStudents"
          />
          <VAutocomplete
            v-model="selectedStudentId"
            :items="studentOptions"
            :loading="studentLoading"
            label="Student"
            density="comfortable"
          />
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn
            variant="text"
            @click="studentDialogOpen = false"
          >
            Cancel
          </VBtn>
          <VBtn
            color="primary"
            :loading="saving"
            :disabled="!selectedStudentId"
            @click="submitFromStudent"
          >
            Create
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </VContainer>
</template>
