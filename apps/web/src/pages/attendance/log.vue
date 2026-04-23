<script setup lang="ts">
import { listAttendance, getExportCSVUrl, createManualCorrection } from '@/api/attendance/events'
import { listUsers } from '@/api/attendance/users'
import type { AttendanceEvent } from '@/api/attendance/events'
import type { AttendanceUser } from '@/api/attendance/auth'

definePage({ meta: { public: true, layout: 'blank' } })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const events = ref<AttendanceEvent[]>([])
const users = ref<AttendanceUser[]>([])
const loading = ref(true)

const filters = reactive({
  user_id: '' as string,
  date_from: '',
  date_to: '',
  event_type: '' as string,
})
const page = ref(1)

const correctionDialog = ref(false)
const correctionForm = reactive({
  user_id: '',
  event_type: 'manual_correction',
  notes: '',
})
const correcting = ref(false)

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) { router.replace({ name: 'attendance-login' }); return }

  if (authStore.isStaffOrAdmin) {
    try { users.value = await listUsers() } catch {}
  }
  await loadEvents()
})

async function loadEvents() {
  loading.value = true
  try {
    events.value = await listAttendance({
      target_user_id: filters.user_id || undefined,
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

function handleExport() {
  const url = getExportCSVUrl({
    target_user_id: filters.user_id || undefined,
    date_from: filters.date_from ? `${filters.date_from}T00:00:00Z` : undefined,
    date_to: filters.date_to ? `${filters.date_to}T23:59:59Z` : undefined,
  })
  window.open(url, '_blank')
}

async function handleCorrection() {
  correcting.value = true
  try {
    await createManualCorrection({
      user_id: correctionForm.user_id,
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

function handleLogout() {
  authStore.logout()
  router.push({ name: 'attendance-login' })
}
</script>

<template>
  <VApp>
    <VAppBar color="primary" density="compact">
      <VBtn icon variant="text" :to="{ name: authStore.isStaffOrAdmin ? 'attendance-dashboard' : 'attendance-my-qr' }">
        <VIcon icon="ri-arrow-left-line" />
      </VBtn>
      <VAppBarTitle>Attendance Log</VAppBarTitle>
      <VSpacer />
      <VBtn icon variant="text" @click="handleLogout">
        <VIcon icon="ri-logout-box-r-line" />
      </VBtn>
    </VAppBar>

    <VMain>
      <VContainer>
        <!-- Filters -->
        <VCard class="mb-4 pa-4" v-if="authStore.isStaffOrAdmin">
          <VRow dense align="end">
            <VCol cols="12" sm="3">
              <VSelect
                v-model="filters.user_id"
                :items="[{ title: 'All Users', value: '' }, ...users.map(u => ({ title: `${u.full_name || u.username} (${u.role})`, value: u.id }))]"
                label="User"
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
            <VCol cols="12" sm="2">
              <VSelect
                v-model="filters.event_type"
                :items="[{ title: 'All Types', value: '' }, { title: 'Check In', value: 'check_in' }, { title: 'Check Out', value: 'check_out' }, { title: 'Correction', value: 'manual_correction' }]"
                label="Type"
                density="compact"
                hide-details
              />
            </VCol>
            <VCol cols="12" sm="3" class="d-flex gap-2">
              <VBtn color="primary" @click="loadEvents" prepend-icon="ri-search-line">
                Filter
              </VBtn>
              <VBtn variant="outlined" @click="handleExport" prepend-icon="ri-download-line">
                CSV
              </VBtn>
              <VBtn v-if="authStore.isAdmin" variant="tonal" color="info" @click="correctionDialog = true" prepend-icon="ri-add-line">
                Manual
              </VBtn>
            </VCol>
          </VRow>
        </VCard>

        <!-- Table -->
        <VCard :loading="loading">
          <VTable>
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>User</th>
                <th>Type</th>
                <th>Scanner</th>
                <th>Device</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="evt in events" :key="evt.id">
                <td>{{ formatDateTime(evt.recorded_at) }}</td>
                <td>{{ evt.full_name || evt.username || evt.user_id }}</td>
                <td>
                  <VChip :color="eventColor(evt.event_type)" size="small" label>
                    {{ evt.event_type.replace('_', ' ') }}
                  </VChip>
                </td>
                <td>{{ evt.scanner_user_id ? evt.scanner_user_id.substring(0, 8) + '...' : '—' }}</td>
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

        <!-- Manual correction dialog -->
        <VDialog v-model="correctionDialog" max-width="500">
          <VCard>
            <VCardTitle>Manual Correction</VCardTitle>
            <VCardText>
              <VForm @submit.prevent="handleCorrection">
                <VSelect
                  v-model="correctionForm.user_id"
                  :items="users.map(u => ({ title: `${u.full_name || u.username}`, value: u.id }))"
                  label="User"
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
                  <VBtn variant="outlined" @click="correctionDialog = false">
                    Cancel
                  </VBtn>
                  <VBtn type="submit" color="primary" :loading="correcting">
                    Save
                  </VBtn>
                </div>
              </VForm>
            </VCardText>
          </VCard>
        </VDialog>
      </VContainer>
    </VMain>
  </VApp>
</template>
