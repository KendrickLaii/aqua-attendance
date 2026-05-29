<script setup lang="ts">
import { useAbility } from '@casl/vue'
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { attendanceRoleToCaslRules } from '@/utils/attendanceCasl'
import { formatApiError } from '@/utils/formatApiDetail'

definePage({
  meta: {
    public: true,
    layout: 'blank',
  },
})

const authStore = useAttendanceAuthStore()
const router = useRouter()
const route = useRoute()
const ability = useAbility()

const form = reactive({ username: '', password: '' })
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')

function resolvePostLoginTarget(): string | { name: 'attendance-dashboard' } {
  const raw = route.query.to
  const target = typeof raw === 'string'
    ? raw.trim()
    : Array.isArray(raw)
      ? raw[0]?.trim() ?? ''
      : ''

  if (
    target.startsWith('/attendance')
    && target !== '/attendance'
    && !target.startsWith('/attendance/login')
  )
    return target

  return { name: 'attendance-dashboard' }
}

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login({ username: form.username.trim(), password: form.password })

    const userData = {
      id: authStore.user?.id,
      username: authStore.user?.username,
      role: authStore.user?.role,
      fullName: authStore.user?.full_name,
    }

    const userAbilityRules = attendanceRoleToCaslRules(authStore.user?.role)

    useCookie('userData').value = userData as any
    useCookie('accessToken').value = useCookie('attendanceAccessToken').value
    useCookie('userAbilityRules').value = userAbilityRules as any
    ability.update(userAbilityRules)

    await router.push(resolvePostLoginTarget())
  }
  catch (e: unknown) {
    error.value = formatApiError(e, 'Login failed. Check credentials.')
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
          :rules="[requiredValidator]"
        />
        <VTextField
          v-model="form.password"
          label="Password"
          :type="showPassword ? 'text' : 'password'"
          prepend-inner-icon="ri-lock-line"
          autocomplete="current-password"
          class="mb-4"
          :rules="[requiredValidator]"
        >
          <template #append-inner>
            <VIcon
              :icon="showPassword ? 'ri-eye-off-line' : 'ri-eye-line'"
              style="cursor: pointer"
              @click="showPassword = !showPassword"
            />
          </template>
        </VTextField>
        <VBtn type="submit" block color="primary" :loading="loading" size="large">
          Sign In
        </VBtn>
      </VForm>
    </VCard>
  </div>
</template>
