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
  if (authStore.isLoggedIn)
    router.replace({ name: 'attendance-dashboard' })
  else
    router.replace({ name: 'attendance-login' })
})
</script>

<template>
  <div class="d-flex align-center justify-center" style="min-height: 100vh">
    <VProgressCircular indeterminate color="primary" size="48" />
  </div>
</template>
