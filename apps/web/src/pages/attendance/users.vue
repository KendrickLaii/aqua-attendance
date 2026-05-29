<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import {
  attendanceCreatePasswordValidator,
  internalEmailValidator,
  maxCharsRule,
  requiredValidator,
  usernameAttendanceValidator,
} from '@core/utils/validators'
import { createUser, deleteUser, listUsers, updateUser } from '@/api/attendance/users'
import type { AttendanceUser } from '@/api/attendance/auth'
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { formatApiDetail } from '@/utils/formatApiDetail'

definePage({ meta: { action: 'manage', subject: 'User' } })

const authStore = useAttendanceAuthStore()
const router = useRouter()

const users = ref<AttendanceUser[]>([])
const loading = ref(true)
const dialogOpen = ref(false)
const editingUser = ref<AttendanceUser | null>(null)

const form = reactive({
  username: '',
  email: '',
  password: '',
  full_name: '',
  role: 'admin' as string,
  is_active: true,
})

const saving = ref(false)
const saveError = ref<string | null>(null)
const searchQuery = ref('')
const showPassword = ref(false)

const userFormRef = ref<VForm>()

const usernameRules = [requiredValidator, usernameAttendanceValidator] as const
const emailRules = [requiredValidator, internalEmailValidator] as const
const fullNameRules = [requiredValidator, maxCharsRule(255, 'Full name')] as const
const createPasswordRules = [requiredValidator, attendanceCreatePasswordValidator] as const
const editPasswordRules = [attendanceCreatePasswordValidator] as const

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isAdmin) {
    router.replace({ name: 'attendance-login' })
    return
  }
  await loadUsers()
})

async function loadUsers() {
  loading.value = true
  try {
    users.value = await listUsers({ search: searchQuery.value || undefined })
  }
  finally {
    loading.value = false
  }
}

function openCreate() {
  saveError.value = null
  editingUser.value = null
  showPassword.value = false
  Object.assign(form, {
    username: '', email: '', password: '', full_name: '',
    role: 'admin', is_active: true,
  })
  dialogOpen.value = true
  nextTick(() => userFormRef.value?.resetValidation())
}

function openEdit(u: AttendanceUser) {
  saveError.value = null
  editingUser.value = u
  showPassword.value = false
  Object.assign(form, {
    username: u.username, email: u.email, password: '',
    full_name: u.full_name, role: u.role, is_active: u.is_active,
  })
  dialogOpen.value = true
  nextTick(() => userFormRef.value?.resetValidation())
}

async function handleSave() {
  saveError.value = null
  const validation = await userFormRef.value?.validate()
  if (validation && !validation.valid) return

  saving.value = true
  try {
    if (editingUser.value) {
      const updatePayload: Record<string, any> = {
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        role: form.role,
        is_active: form.is_active,
      }
      if (form.password.trim())
        updatePayload.password = form.password.trim()
      await updateUser(editingUser.value.id, updatePayload)
    }
    else {
      await createUser({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        role: form.role,
      })
    }
    dialogOpen.value = false
    await loadUsers()
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined
    saveError.value = formatApiDetail(data?.detail) || (e instanceof Error ? e.message : 'Could not save user')
  }
  finally {
    saving.value = false
  }
}

async function handleDelete(u: AttendanceUser) {
  if (!confirm(`Delete admin user ${u.username}?`)) return
  await deleteUser(u.id)
  await loadUsers()
}

function roleColor(role: string) {
  if (role === 'superadmin') return 'error'
  return 'warning'
}

/** Admins may edit/delete admin accounts only; superadmins may manage all. */
function canManageUser(u: AttendanceUser) {
  return authStore.isSuperAdmin || u.role === 'admin'
}

const roleOptions = computed(() =>
  authStore.isSuperAdmin
    ? ['admin', 'superadmin']
    : ['admin'],
)
</script>

<template>
  <VContainer>
    <VRow class="mb-4" align="center">
      <VCol cols="12" sm="6">
        <VTextField
          v-model="searchQuery"
          placeholder="Search admin users..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          @update:model-value="loadUsers"
        />
      </VCol>
      <VCol cols="12" sm="6" class="text-end">
        <VBtn color="primary" prepend-icon="ri-add-line" @click="openCreate">
          Add Admin User
        </VBtn>
      </VCol>
    </VRow>

    <VCard :loading="loading">
      <VTable>
        <thead>
          <tr>
            <th>Username</th>
            <th>Full Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Active</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td class="font-weight-medium">{{ u.username }}</td>
            <td>{{ u.full_name }}</td>
            <td>{{ u.email }}</td>
            <td>
              <VChip :color="roleColor(u.role)" size="small" label>
                {{ u.role }}
              </VChip>
            </td>
            <td>
              <VIcon :icon="u.is_active ? 'ri-checkbox-circle-fill' : 'ri-close-circle-fill'" :color="u.is_active ? 'success' : 'error'" />
            </td>
            <td>
              <VBtn
                v-if="canManageUser(u)"
                icon
                size="small"
                variant="text"
                title="Edit"
                @click="openEdit(u)"
              >
                <VIcon icon="ri-edit-line" />
              </VBtn>
              <VBtn
                v-if="authStore.isSuperAdmin"
                icon
                size="small"
                variant="text"
                color="error"
                title="Delete"
                @click="handleDelete(u)"
              >
                <VIcon icon="ri-delete-bin-line" />
              </VBtn>
            </td>
          </tr>
        </tbody>
      </VTable>
    </VCard>

    <VDialog v-model="dialogOpen" max-width="500" scrollable>
      <VCard>
        <VCardTitle class="text-h6 py-4">
          {{ editingUser ? 'Edit Admin User' : 'Create Admin User' }}
        </VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <VAlert v-if="saveError" type="error" variant="tonal" density="compact" class="mb-4" closable @click:close="saveError = null">
            {{ saveError }}
          </VAlert>
          <VForm ref="userFormRef" @submit.prevent="handleSave">
            <VTextField
              v-model="form.username"
              label="Username *"
              :disabled="!!editingUser"
              maxlength="100"
              :rules="usernameRules"
              class="mb-3"
            />
            <VTextField
              v-model="form.full_name"
              label="Full name *"
              maxlength="255"
              :rules="fullNameRules"
              class="mb-3"
            />
            <VTextField
              v-model="form.email"
              label="Email *"
              type="email"
              maxlength="255"
              :rules="emailRules"
              class="mb-3"
            />
            <VTextField
              v-model="form.password"
              :label="editingUser ? 'New Password (leave blank to keep current)' : 'Password *'"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="new-password"
              maxlength="128"
              :rules="editingUser ? (form.password ? editPasswordRules : []) : createPasswordRules"
              class="mb-3"
            >
              <template #append-inner>
                <VIcon
                  :icon="showPassword ? 'ri-eye-off-line' : 'ri-eye-line'"
                  style="cursor: pointer"
                  @click="showPassword = !showPassword"
                />
              </template>
            </VTextField>
            <VSelect
              v-model="form.role"
              :items="roleOptions"
              label="Role"
              class="mb-3"
            />
            <VSwitch
              v-if="editingUser"
              v-model="form.is_active"
              label="Login access enabled"
              class="mb-3"
            />
            <div class="d-flex justify-end gap-2 mt-2">
              <VBtn variant="text" @click="dialogOpen = false">Cancel</VBtn>
              <VBtn type="submit" color="primary" :loading="saving">Save</VBtn>
            </div>
          </VForm>
        </VCardText>
      </VCard>
    </VDialog>
  </VContainer>
</template>
