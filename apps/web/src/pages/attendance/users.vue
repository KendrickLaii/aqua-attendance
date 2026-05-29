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
import { formatApiError } from '@/utils/formatApiDetail'

definePage({ meta: { action: 'manage', subject: 'User' } })

const USER_PAGE_SIZE = 200
const SEARCH_DEBOUNCE_MS = 300

const authStore = useAttendanceAuthStore()
const router = useRouter()

const users = ref<AttendanceUser[]>([])
const loading = ref(true)
const refreshing = ref(false)
const loadError = ref('')
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
const saveError = ref('')
const searchQuery = ref('')
const showPassword = ref(false)

const deleteConfirmOpen = ref(false)
const deleteTarget = ref<AttendanceUser | null>(null)
const deleting = ref(false)
const deleteError = ref('')

const userFormRef = ref<VForm>()

const usernameRules = [requiredValidator, usernameAttendanceValidator] as const
const emailRules = [requiredValidator, internalEmailValidator] as const
const fullNameRules = [requiredValidator, maxCharsRule(255, 'Full name')] as const
const createPasswordRules = [requiredValidator, attendanceCreatePasswordValidator] as const
const editPasswordRules = [attendanceCreatePasswordValidator] as const

const usersCapped = computed(() => users.value.length >= USER_PAGE_SIZE)
const activeCount = computed(() => users.value.filter(u => u.is_active).length)

const pageSubtitle = computed(() => {
  if (loading.value && !refreshing.value)
    return 'Loading…'

  const total = users.value.length
  const countLabel = usersCapped.value ? `${USER_PAGE_SIZE}+` : String(total)

  return `${countLabel} users · ${activeCount.value} login enabled`
})

const listCaption = computed(() => {
  if (loading.value || users.value.length === 0)
    return ''

  const total = users.value.length
  if (usersCapped.value)
    return `Showing ${total} of ${USER_PAGE_SIZE}+ users`
  if (searchQuery.value.trim())
    return `Showing ${total} matching user${total === 1 ? '' : 's'}`

  return `${total} user${total === 1 ? '' : 's'}`
})

const showEmptyCreateCta = computed(() => !searchQuery.value.trim())

const roleSelectItems = computed(() => {
  if (authStore.isSuperAdmin) {
    return [
      { title: 'Admin', value: 'admin' },
      { title: 'Super Admin', value: 'superadmin' },
    ]
  }

  return [{ title: 'Admin', value: 'admin' }]
})

onMounted(async () => {
  authStore.restoreSession()
  if (!authStore.isLoggedIn) {
    router.replace({ name: 'attendance-login' })

    return
  }
  if (!authStore.isAdmin) {
    router.replace({ name: 'attendance-dashboard' })

    return
  }
  await loadUsers()
})

async function loadUsers(isRefresh = false) {
  const softRefresh = isRefresh === true

  if (softRefresh)
    refreshing.value = true
  else
    loading.value = true
  loadError.value = ''
  try {
    users.value = await listUsers({
      search: searchQuery.value.trim() || undefined,
      page_size: USER_PAGE_SIZE,
    })
  }
  catch (e) {
    console.error('Failed to load users', e)
    loadError.value = 'Failed to load admin users. Please try again.'
  }
  finally {
    loading.value = false
    refreshing.value = false
  }
}

const debouncedLoadUsers = useDebounceFn(() => loadUsers(true), SEARCH_DEBOUNCE_MS)

watch(searchQuery, () => {
  debouncedLoadUsers()
})

function closeEditDialog() {
  dialogOpen.value = false
  saveError.value = ''
}

function openCreate() {
  saveError.value = ''
  editingUser.value = null
  showPassword.value = false
  Object.assign(form, {
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'admin',
    is_active: true,
  })
  dialogOpen.value = true
  nextTick(() => userFormRef.value?.resetValidation())
}

function openEdit(u: AttendanceUser) {
  saveError.value = ''
  editingUser.value = u
  showPassword.value = false
  Object.assign(form, {
    username: u.username,
    email: u.email,
    password: '',
    full_name: u.full_name,
    role: u.role,
    is_active: u.is_active,
  })
  dialogOpen.value = true
  nextTick(() => userFormRef.value?.resetValidation())
}

async function handleSave() {
  saveError.value = ''

  const validation = await userFormRef.value?.validate()
  if (validation && !validation.valid)
    return

  saving.value = true
  try {
    if (editingUser.value) {
      const updatePayload: {
        email: string
        full_name: string
        role: string
        is_active: boolean
        password?: string
      } = {
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
    closeEditDialog()
    await loadUsers(true)
  }
  catch (e: unknown) {
    saveError.value = formatApiError(e, 'Could not save user')
  }
  finally {
    saving.value = false
  }
}

function openDeleteConfirm(u: AttendanceUser) {
  deleteError.value = ''
  deleteTarget.value = u
  deleteConfirmOpen.value = true
}

function closeDeleteConfirm() {
  deleteConfirmOpen.value = false
  deleteError.value = ''
  deleteTarget.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value)
    return

  deleting.value = true
  deleteError.value = ''
  try {
    await deleteUser(deleteTarget.value.id)
    closeDeleteConfirm()
    await loadUsers(true)
  }
  catch (e: unknown) {
    deleteError.value = formatApiError(e, 'Could not delete user')
  }
  finally {
    deleting.value = false
  }
}

function roleColor(role: string) {
  if (role === 'superadmin')
    return 'error'

  return 'warning'
}

function roleLabel(role: string) {
  if (role === 'superadmin')
    return 'Super Admin'
  if (role === 'admin')
    return 'Admin'

  return role
}

/** Admins may edit admin accounts only; superadmins may manage all. */
function canManageUser(u: AttendanceUser) {
  return authStore.isSuperAdmin || u.role === 'admin'
}

function canDeleteUser(u: AttendanceUser) {
  return authStore.isSuperAdmin && u.id !== authStore.user?.id
}
</script>

<template>
  <VContainer>
    <VRow
      class="mb-2"
      align="center"
    >
      <VCol
        cols="12"
        sm="8"
      >
        <div class="text-h5 font-weight-medium">
          Admin Users
        </div>
        <div class="text-body-2 text-medium-emphasis">
          {{ pageSubtitle }}
        </div>
      </VCol>
      <VCol
        cols="12"
        sm="4"
        class="d-flex flex-wrap justify-sm-end gap-2"
      >
        <VBtn
          variant="tonal"
          color="primary"
          prepend-icon="ri-refresh-line"
          :loading="refreshing"
          @click="loadUsers(true)"
        >
          Refresh
        </VBtn>
        <VBtn
          color="primary"
          prepend-icon="ri-add-line"
          @click="openCreate"
        >
          Add Admin User
        </VBtn>
      </VCol>
    </VRow>

    <VRow
      class="mb-4"
      align="center"
    >
      <VCol
        cols="12"
        sm="6"
      >
        <VTextField
          v-model="searchQuery"
          placeholder="Search admin users..."
          prepend-inner-icon="ri-search-line"
          density="compact"
          hide-details
          clearable
        />
      </VCol>
      <VCol
        v-if="listCaption"
        cols="auto"
        class="ms-sm-auto"
      >
        <span class="text-caption text-medium-emphasis">{{ listCaption }}</span>
      </VCol>
    </VRow>

    <VAlert
      v-if="loadError"
      type="error"
      variant="tonal"
      class="mb-4"
      closable
      @click:close="loadError = ''"
    >
      {{ loadError }}
      <template #append>
        <VBtn
          variant="text"
          size="small"
          @click="loadUsers(true)"
        >
          Retry
        </VBtn>
      </template>
    </VAlert>

    <VAlert
      v-if="authStore.isAdmin && !authStore.isSuperAdmin"
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
      icon="ri-information-line"
    >
      You can manage admin accounts only. Super admin accounts require a super admin to edit or delete.
    </VAlert>

    <VCard :loading="loading && !refreshing">
      <VCardTitle class="d-flex align-center justify-space-between flex-wrap gap-2">
        <span>Users</span>
        <span
          v-if="listCaption"
          class="text-caption text-medium-emphasis"
        >
          {{ listCaption }}
        </span>
      </VCardTitle>
      <div class="users-table-scroll">
        <VTable class="users-table">
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
            <tr
              v-for="u in users"
              :key="u.id"
              :class="{ 'user-row-inactive': !u.is_active }"
            >
              <td class="font-weight-medium">
                {{ u.username }}
              </td>
              <td>{{ u.full_name }}</td>
              <td>{{ u.email }}</td>
              <td>
                <VChip
                  :color="roleColor(u.role)"
                  size="small"
                  label
                >
                  {{ roleLabel(u.role) }}
                </VChip>
              </td>
              <td>
                <VIcon
                  :icon="u.is_active ? 'ri-checkbox-circle-fill' : 'ri-close-circle-fill'"
                  :color="u.is_active ? 'success' : 'error'"
                />
              </td>
              <td>
                <VBtn
                  v-if="canManageUser(u)"
                  icon
                  size="small"
                  variant="text"
                  title="Edit"
                  :aria-label="`Edit ${u.username}`"
                  @click="openEdit(u)"
                >
                  <VIcon icon="ri-edit-line" />
                </VBtn>
                <VBtn
                  v-if="canDeleteUser(u)"
                  icon
                  size="small"
                  variant="text"
                  color="error"
                  title="Delete"
                  :aria-label="`Delete ${u.username}`"
                  @click="openDeleteConfirm(u)"
                >
                  <VIcon icon="ri-delete-bin-line" />
                </VBtn>
              </td>
            </tr>
            <tr v-if="users.length === 0 && !loading && !loadError">
              <td
                colspan="6"
                class="text-center text-medium-emphasis py-6"
              >
                <template v-if="showEmptyCreateCta">
                  No admin users yet. Click <strong>Add Admin User</strong> to create one.
                </template>
                <template v-else>
                  No users match your search.
                </template>
              </td>
            </tr>
          </tbody>
        </VTable>
      </div>
    </VCard>

    <VDialog
      v-model="dialogOpen"
      max-width="500"
      scrollable
    >
      <VCard>
        <VCardTitle class="text-h6 py-4">
          {{ editingUser ? 'Edit Admin User' : 'Create Admin User' }}
        </VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <VAlert
            v-if="saveError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-4"
            closable
            @click:close="saveError = ''"
          >
            {{ saveError }}
          </VAlert>
          <VForm
            ref="userFormRef"
            @submit.prevent="handleSave"
          >
            <VTextField
              v-model="form.username"
              label="Username *"
              :disabled="!!editingUser"
              maxlength="100"
              :rules="usernameRules"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VTextField
              v-model="form.full_name"
              label="Full name *"
              maxlength="255"
              :rules="fullNameRules"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VTextField
              v-model="form.email"
              label="Email *"
              type="email"
              maxlength="255"
              :rules="emailRules"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VTextField
              v-model="form.password"
              :label="editingUser ? 'New Password (leave blank to keep current)' : 'Password *'"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="new-password"
              maxlength="128"
              :rules="editingUser ? (form.password ? editPasswordRules : []) : createPasswordRules"
              density="compact"
              variant="outlined"
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
              :items="roleSelectItems"
              label="Role"
              density="compact"
              variant="outlined"
              class="mb-3"
            />
            <VSwitch
              v-if="editingUser"
              v-model="form.is_active"
              label="Login access enabled"
              color="success"
              inset
              class="mb-1"
            />
          </VForm>
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            @click="closeEditDialog"
          >
            Cancel
          </VBtn>
          <VBtn
            variant="flat"
            color="primary"
            :loading="saving"
            @click="handleSave"
          >
            Save
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>

    <VDialog
      v-model="deleteConfirmOpen"
      max-width="420"
      persistent
    >
      <VCard>
        <VCardTitle>Delete {{ deleteTarget?.username }}?</VCardTitle>
        <VCardText>
          <VAlert
            v-if="deleteError"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-3"
            closable
            @click:close="deleteError = ''"
          >
            {{ deleteError }}
          </VAlert>
          <template v-if="deleteTarget">
            This will permanently remove admin user
            <strong>{{ deleteTarget.username }}</strong> ({{ deleteTarget.full_name }}).
            This action cannot be undone.
          </template>
        </VCardText>
        <VDivider />
        <DialogFooter>
          <VBtn
            variant="outlined"
            color="primary"
            @click="closeDeleteConfirm"
          >
            Cancel
          </VBtn>
          <VBtn
            variant="flat"
            color="error"
            :loading="deleting"
            @click="confirmDelete"
          >
            Delete
          </VBtn>
        </DialogFooter>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.user-row-inactive {
  opacity: 0.55;
}

.users-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
</style>
