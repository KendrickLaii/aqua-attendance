<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listAttendance, exportAttendanceCSV, createManualCorrection } from '@/api/attendance/events'
import { listProducts } from '@/api/attendance/products'
import type { AttendanceEvent } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'

definePage({ meta: {} })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const events = ref<AttendanceEvent[]>([])
const products = ref<Product[]>([])
const loading = ref(true)

const filters = reactive({
  product_id: '' as string,
  product_type: '' as string,
  date_from: '',
  date_to: '',
  event_type: '' as string,
})
const page = ref(1)

const correctionDialog = ref(false)
const correctionForm = reactive({
  product_id: '',
  event_type: 'manual_correction',
  notes: '',
})
const correcting = ref(false)
const exporting = ref(false)
const exportError = ref('')

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) { router.replace({ name: 'attendance-login' }); return }

  try { products.value = await listProducts() } catch {}
  await loadEvents()
})

async function loadEvents() {
  loading.value = true
  try {
    events.value = await listAttendance({
      product_id: filters.product_id || undefined,
      product_type: filters.product_type || undefined,
      date_from: filters.date_from ? `${filters.date_from}T00:00:00Z` : undefined,
      date_to: filters.date_to ? `${filters.date_to}T23:59:59Z` : undefined,
      event_type: filters.event_type || undefined,
      page: page.value,
      page_size: 100,
    })
  }
  finally {
    loading.value = false
  }
}

function formatDateTime(iso: string) {
  const d = new Date(iso)
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

function eventColor(type: string) {
  if (type === 'check_in') return 'success'
  if (type === 'check_out') return 'warning'
  return 'info'
}

async function handleExport() {
  exporting.value = true
  exportError.value = ''
  try {
    const blob = await exportAttendanceCSV({
      product_id: filters.product_id || undefined,
      product_type: filters.product_type || undefined,
      date_from: filters.date_from ? `${filters.date_from}T00:00:00Z` : undefined,
      date_to: filters.date_to ? `${filters.date_to}T23:59:59Z` : undefined,
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'attendance_export.csv'
    link.click()
    URL.revokeObjectURL(url)
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined
    exportError.value = typeof data?.detail === 'string' ? data.detail : 'Export failed'
  }
  finally {
    exporting.value = false
  }
}

async function handleCorrection() {
  correcting.value = true
  try {
    await createManualCorrection({
      product_id: correctionForm.product_id,
      event_type: correctionForm.event_type,
      notes: correctionForm.notes || undefined,
    })
    correctionDialog.value = false
    await loadEvents()
  }
  finally {
    correcting.value = false
  }
}
</script>

<template>
  <VContainer>
    <VCard class="mb-4 pa-4">
      <VRow dense align="end">
        <VCol cols="12" sm="3">
          <VSelect
            v-model="filters.product_id"
            :items="[{ title: 'All Products', value: '' }, ...products.map(p => ({ title: `${p.full_name} (${p.code})`, value: p.id }))]"
            label="Product"
            density="compact"
            hide-details
          />
        </VCol>
        <VCol cols="12" sm="2">
          <VSelect
            v-model="filters.product_type"
            :items="[{ title: 'All Types', value: '' }, { title: 'Staff', value: 'staff' }, { title: 'Student', value: 'student' }]"
            label="Type"
            density="compact"
            hide-details
          />
        </VCol>
        <VCol cols="12" sm="2">
          <VTextField v-model="filters.date_from" label="From" type="date" density="compact" hide-details />
        </VCol>
        <VCol cols="12" sm="2">
          <VTextField v-model="filters.date_to" label="To" type="date" density="compact" hide-details />
        </VCol>
        <VCol cols="12" sm="3" class="d-flex gap-2">
          <VBtn color="primary" @click="loadEvents" prepend-icon="ri-search-line">
            Filter
          </VBtn>
          <VBtn
            variant="outlined"
            :loading="exporting"
            :disabled="exporting"
            prepend-icon="ri-download-line"
            @click="handleExport"
          >
            CSV
          </VBtn>
          <VBtn variant="tonal" color="info" @click="correctionDialog = true" prepend-icon="ri-add-line">
            Manual
          </VBtn>
        </VCol>
      </VRow>
    </VCard>

    <VAlert v-if="exportError" type="error" variant="tonal" class="mb-4" closable @click:close="exportError = ''">
      {{ exportError }}
    </VAlert>

    <VCard :loading="loading">
      <VTable>
        <thead>
          <tr>
            <th>Date / Time</th>
            <th>Product</th>
            <th>Type</th>
            <th>Event</th>
            <th>Device</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="evt in events" :key="evt.id">
            <td>{{ formatDateTime(evt.recorded_at) }}</td>
            <td>{{ evt.product_name || evt.product_code || evt.product_id }}</td>
            <td>
              <VChip v-if="evt.product_type" :color="evt.product_type === 'staff' ? 'info' : 'success'" size="x-small" label>
                {{ evt.product_type }}
              </VChip>
              <span v-else>—</span>
            </td>
            <td>
              <VChip :color="eventColor(evt.event_type)" size="small" label>
                {{ evt.event_type.replace('_', ' ') }}
              </VChip>
            </td>
            <td>{{ evt.client_device_id || '—' }}</td>
            <td>{{ evt.notes || '—' }}</td>
          </tr>
          <tr v-if="events.length === 0 && !loading">
            <td colspan="6" class="text-center text-medium-emphasis py-6">
              No attendance records found
            </td>
          </tr>
        </tbody>
      </VTable>
    </VCard>

    <VDialog v-model="correctionDialog" max-width="500">
      <VCard>
        <VCardTitle>Manual Correction</VCardTitle>
        <VCardText>
          <VForm @submit.prevent="handleCorrection">
            <VSelect
              v-model="correctionForm.product_id"
              :items="products.map(p => ({ title: `${p.full_name} (${p.code})`, value: p.id }))"
              label="Product"
              class="mb-3"
              required
            />
            <VSelect
              v-model="correctionForm.event_type"
              :items="[{ title: 'Check In', value: 'check_in' }, { title: 'Check Out', value: 'check_out' }, { title: 'Manual Correction', value: 'manual_correction' }]"
              label="Event Type"
              class="mb-3"
            />
            <VTextarea v-model="correctionForm.notes" label="Notes" rows="2" class="mb-3" />
            <div class="d-flex justify-end gap-2">
              <VBtn variant="outlined" @click="correctionDialog = false">Cancel</VBtn>
              <VBtn type="submit" color="primary" :loading="correcting">Save</VBtn>
            </div>
          </VForm>
        </VCardText>
      </VCard>
    </VDialog>
  </VContainer>
</template>
