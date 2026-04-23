<script setup lang="ts">
import { listAttendance } from '@/api/attendance/events'
import { listUsers } from '@/api/attendance/users'
import type { AttendanceEvent } from '@/api/attendance/events'
import type { AttendanceUser } from '@/api/attendance/auth'

definePage({ meta: { public: true, layout: 'blank' } })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const recentEvents = ref<AttendanceEvent[]>([])
const userCount = ref(0)
const todayCheckIns = ref(0)
const todayCheckOuts = ref(0)
const loading = ref(true)

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) { router.replace({ name: 'attendance-login' }); return }
  if (!authStore.isStaffOrAdmin) { router.replace({ name: 'attendance-my-qr' }); return }

  try {
    const today = new Date().toISOString().split('T')[0]
    const [events, users] = await Promise.all([
      listAttendance({ date_from: `${today}T00:00:00Z`, page_size: 20 }),
      authStore.isAdmin ? listUsers() : Promise.resolve([]),
    ])
    recentEvents.value = events
    userCount.value = users.length
    todayCheckIns.value = events.filter(e => e.event_type === 'check_in').length
    todayCheckOuts.value = events.filter(e => e.event_type === 'check_out').length
  }
  catch (e) {
    console.error('Failed to load dashboard', e)
  }
  finally {
    loading.value = false
  }
})

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function eventColor(type: string) {
  if (type === 'check_in') return 'success'
  if (type === 'check_out') return 'warning'
  return 'info'
}

function handleLogout() {
  authStore.logout()
  router.push({ name: 'attendance-login' })
}
</script>

<template>
  <VApp>
    <VAppBar color="primary" density="compact">
      <VAppBarTitle>Juku Attendance — Dashboard</VAppBarTitle>
      <VSpacer />
      <VBtn variant="text" :to="{ name: 'attendance-scanner' }" class="me-2">
        <VIcon icon="ri-qr-scan-2-line" class="me-1" />
        Scanner
      </VBtn>
      <VBtn variant="text" :to="{ name: 'attendance-log' }" class="me-2">
        <VIcon icon="ri-list-check-line" class="me-1" />
        Log
      </VBtn>
      <VBtn v-if="authStore.isAdmin" variant="text" :to="{ name: 'attendance-users' }" class="me-2">
        <VIcon icon="ri-group-line" class="me-1" />
        Users
      </VBtn>
      <VBtn icon variant="text" @click="handleLogout">
        <VIcon icon="ri-logout-box-r-line" />
      </VBtn>
    </VAppBar>

    <VMain>
      <VContainer>
        <VRow v-if="loading">
          <VCol cols="12" class="text-center py-12">
            <VProgressCircular indeterminate color="primary" size="48" />
          </VCol>
        </VRow>

        <template v-else>
          <VRow class="mb-4">
            <VCol cols="12" sm="4">
              <VCard color="success" variant="tonal">
                <VCardText class="text-center">
                  <div class="text-h4 font-weight-bold">
                    {{ todayCheckIns }}
                  </div>
                  <div class="text-body-1">
                    Check-ins Today
                  </div>
                </VCardText>
              </VCard>
            </VCol>
            <VCol cols="12" sm="4">
              <VCard color="warning" variant="tonal">
                <VCardText class="text-center">
                  <div class="text-h4 font-weight-bold">
                    {{ todayCheckOuts }}
                  </div>
                  <div class="text-body-1">
                    Check-outs Today
                  </div>
                </VCardText>
              </VCard>
            </VCol>
            <VCol v-if="authStore.isAdmin" cols="12" sm="4">
              <VCard color="info" variant="tonal">
                <VCardText class="text-center">
                  <div class="text-h4 font-weight-bold">
                    {{ userCount }}
                  </div>
                  <div class="text-body-1">
                    Total Users
                  </div>
                </VCardText>
              </VCard>
            </VCol>
          </VRow>

          <VCard>
            <VCardTitle>Recent Activity Today</VCardTitle>
            <VTable>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Type</th>
                  <th>Device</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="evt in recentEvents" :key="evt.id">
                  <td>{{ formatTime(evt.recorded_at) }}</td>
                  <td>{{ evt.full_name || evt.username }}</td>
                  <td>
                    <VChip :color="eventColor(evt.event_type)" size="small" label>
                      {{ evt.event_type.replace('_', ' ') }}
                    </VChip>
                  </td>
                  <td>{{ evt.client_device_id || '—' }}</td>
                </tr>
                <tr v-if="recentEvents.length === 0">
                  <td colspan="4" class="text-center text-medium-emphasis py-4">
                    No events today
                  </td>
                </tr>
              </tbody>
            </VTable>
          </VCard>
        </template>
      </VContainer>
    </VMain>
  </VApp>
</template>
