<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { listUsers, createUser, updateUser, deleteUser } from '@/api/attendance/users'
import type { AttendanceUser } from '@/api/attendance/auth'

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
  role: 'student' as string,
  is_active: true,
})
const saving = ref(false)
const searchQuery = ref('')

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isAdmin) { router.replace({ name: 'attendance-login' }); return }
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
  editingUser.value = null
  Object.assign(form, { username: '', email: '', password: '', full_name: '', role: 'student', is_active: true })
  dialogOpen.value = true
}

function openEdit(u: AttendanceUser) {
  editingUser.value = u
  Object.assign(form, { username: u.username, email: u.email, password: '', full_name: u.full_name, role: u.role, is_active: u.is_active })
  dialogOpen.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editingUser.value) {
      await updateUser(editingUser.value.id, {
        email: form.email,
        full_name: form.full_name,
        role: form.role,
        is_active: form.is_active,
      })
    }
    else {
      await createUser({
        username: form.username,
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        role: form.role,
      })
    }
    dialogOpen.value = false
    await loadUsers()
  }
  finally {
    saving.value = false
  }
}

async function handleDelete(u: AttendanceUser) {
  if (!confirm(`Delete user ${u.username}?`)) return
  await deleteUser(u.id)
  await loadUsers()
}

function roleColor(role: string) {
  if (role === 'admin') return 'error'
  if (role === 'staff') return 'info'
  return 'success'
}
</script>

<template>
  <VContainer>
    <VRow class="mb-4" align="center">
      <VCol cols="12" sm="6">
        <VTextField
          v-model="searchQuery"
          placeholder="Search users..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
          @update:model-value="loadUsers"
        />
      </VCol>
      <VCol cols="12" sm="6" class="text-end">
        <VBtn color="primary" prepend-icon="ri-add-line" @click="openCreate">
          Add User
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
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td>{{ u.full_name }}</td>
            <td>{{ u.email }}</td>
            <td>
              <VChip :color="roleColor(u.role)" size="small" label>
                {{ u.role }}
              </VChip>
            </td>
            <td>
              <VChip :color="u.is_active ? 'success' : 'grey'" size="small" label>
                {{ u.is_active ? 'Active' : 'Inactive' }}
              </VChip>
            </td>
            <td>
              <VBtn icon size="small" variant="text" @click="openEdit(u)">
                <VIcon icon="ri-edit-line" />
              </VBtn>
              <VBtn icon size="small" variant="text" color="error" @click="handleDelete(u)">
                <VIcon icon="ri-delete-bin-line" />
              </VBtn>
            </td>
          </tr>
        </tbody>
      </VTable>
    </VCard>

    <VDialog v-model="dialogOpen" max-width="500">
      <VCard>
        <VCardTitle>{{ editingUser ? 'Edit User' : 'Create User' }}</VCardTitle>
        <VCardText>
          <VForm @submit.prevent="handleSave">
            <VTextField
              v-model="form.username"
              label="Username"
              class="mb-3"
              :disabled="!!editingUser"
              required
            />
            <VTextField v-model="form.full_name" label="Full Name" class="mb-3" required />
            <VTextField v-model="form.email" label="Email" type="email" class="mb-3" required />
            <VTextField
              v-if="!editingUser"
              v-model="form.password"
              label="Password"
              type="password"
              class="mb-3"
              required
            />
            <VSelect
              v-model="form.role"
              :items="['admin', 'staff', 'student']"
              label="Role"
              class="mb-3"
            />
            <VSwitch
              v-if="editingUser"
              v-model="form.is_active"
              label="Active"
              class="mb-3"
            />
            <div class="d-flex justify-end gap-2">
              <VBtn variant="outlined" @click="dialogOpen = false">
                Cancel
              </VBtn>
              <VBtn type="submit" color="primary" :loading="saving">
                Save
              </VBtn>
            </div>
          </VForm>
        </VCardText>
      </VCard>
    </VDialog>
  </VContainer>
</template>
