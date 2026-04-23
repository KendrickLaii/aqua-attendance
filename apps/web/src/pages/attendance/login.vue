<script setup lang="ts">
definePage({
  meta: {
    public: true,
    layout: 'blank',
  },
})

const authStore = useAttendanceAuthStore()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login({ username: form.username, password: form.password })
    if (authStore.isAdmin)
      router.push({ name: 'attendance-dashboard' })
    else if (authStore.isStaff)
      router.push({ name: 'attendance-scanner' })
    else
      router.push({ name: 'attendance-my-qr' })
  }
  catch (e: any) {
    error.value = e?.data?.detail || 'Login failed. Check credentials.'
  }
  finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="d-flex align-center justify-center" style="min-height: 100vh; background: rgb(var(--v-theme-background))">
    <VCard class="pa-6" max-width="440" width="100%">
      <VCardTitle class="text-h5 text-center mb-2">
        <VIcon icon="ri-time-line" class="me-2" />
        Juku Attendance
      </VCardTitle>
      <VCardSubtitle class="text-center mb-4">
        Sign in to continue
      </VCardSubtitle>

      <VAlert v-if="error" type="error" variant="tonal" class="mb-4" closable @click:close="error = ''">
        {{ error }}
      </VAlert>

      <VForm @submit.prevent="handleLogin">
        <VTextField
          v-model="form.username"
          label="Username"
          prepend-inner-icon="ri-user-line"
          class="mb-3"
          required
        />
        <VTextField
          v-model="form.password"
          label="Password"
          type="password"
          prepend-inner-icon="ri-lock-line"
          class="mb-4"
          required
        />
        <VBtn type="submit" block color="primary" :loading="loading" size="large">
          Sign In
        </VBtn>
      </VForm>
    </VCard>
  </div>
</template>
