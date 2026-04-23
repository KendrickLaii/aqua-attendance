<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listAttendance } from '@/api/attendance/events'
import { listUsers } from '@/api/attendance/users'
import type { AttendanceEvent } from '@/api/attendance/events'

definePage({ meta: {} })

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
</script>

<template>
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
              <div class="text-h4 font-weight-bold">{{ todayCheckIns }}</div>
              <div class="text-body-1">Check-ins Today</div>
            </VCardText>
          </VCard>
        </VCol>
        <VCol cols="12" sm="4">
          <VCard color="warning" variant="tonal">
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">{{ todayCheckOuts }}</div>
              <div class="text-body-1">Check-outs Today</div>
            </VCardText>
          </VCard>
        </VCol>
        <VCol v-if="authStore.isAdmin" cols="12" sm="4">
          <VCard color="info" variant="tonal">
            <VCardText class="text-center">
              <div class="text-h4 font-weight-bold">{{ userCount }}</div>
              <div class="text-body-1">Total Users</div>
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
</template>
