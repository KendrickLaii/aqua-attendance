<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'

definePage({
  meta: {
    public: true,
    layout: 'blank',
  },
})

const router = useRouter()
const authStore = useAttendanceAuthStore()

onMounted(() => {
  authStore.restoreSession()
  if (authStore.isLoggedIn) {
    if (authStore.isAdmin)
      router.replace({ name: 'attendance-dashboard' })
    else if (authStore.isStaff)
      router.replace({ name: 'attendance-dashboard' })
    else
      router.replace({ name: 'attendance-my-qr' })
  }
  else {
    router.replace({ name: 'attendance-login' })
  }
})
</script>

<template>
  <div class="d-flex align-center justify-center" style="min-height: 100vh">
    <VProgressCircular indeterminate color="primary" size="48" />
  </div>
</template>
