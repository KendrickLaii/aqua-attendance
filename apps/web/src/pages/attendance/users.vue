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
  status: 'inactive',
  gender: '',
  date_of_birth: '',
  phone: '',
  address: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  remarks: '',
  student_code: '',
  english_name: '',
  school_name: '',
  grade_class: '',
  guardian1_name: '',
  guardian1_relationship: '',
  guardian1_phone: '',
  guardian2_name: '',
  guardian2_relationship: '',
  guardian2_phone: '',
  whatsapp_enabled: true,
})

const saving = ref(false)
const saveError = ref<string | null>(null)
const searchQuery = ref('')

const statusOptions = [
  { title: 'Not Activated', value: 'inactive' },
  { title: 'Active', value: 'active' },
  { title: 'Suspended', value: 'suspended' },
]

const genderOptions = [
  { title: 'Male', value: 'male' },
  { title: 'Female', value: 'female' },
  { title: 'Other', value: 'other' },
]

const relationshipOptions = [
  'Father',
  'Mother',
  'Guardian',
  'Brother/Sister',
  'Grandparent',
  'Other',
]

const isStudentRole = computed(() => form.role === 'student')

const userFormRef = ref<VForm>()

const usernameRules = [requiredValidator, usernameAttendanceValidator] as const
const emailRules = [requiredValidator, internalEmailValidator] as const
const fullNameRules = [requiredValidator, maxCharsRule(255, 'Full name')] as const
const createPasswordRules = [requiredValidator, attendanceCreatePasswordValidator] as const

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
  Object.assign(form, {
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'student',
    is_active: true,
    status: 'inactive',
    gender: '',
    date_of_birth: '',
    phone: '',
    address: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    remarks: '',
    student_code: '',
    english_name: '',
    school_name: '',
    grade_class: '',
    guardian1_name: '',
    guardian1_relationship: '',
    guardian1_phone: '',
    guardian2_name: '',
    guardian2_relationship: '',
    guardian2_phone: '',
    whatsapp_enabled: true,
  })
  dialogOpen.value = true
  nextTick(() => userFormRef.value?.resetValidation())
}

function openEdit(u: AttendanceUser) {
  saveError.value = null
  editingUser.value = u
  Object.assign(form, {
    username: u.username,
    email: u.email,
    password: '',
    full_name: u.full_name,
    role: u.role,
    is_active: u.is_active,
    status: u.status ?? 'inactive',
    gender: u.gender ?? '',
    date_of_birth: u.date_of_birth ?? '',
    phone: u.phone ?? '',
    address: u.address ?? '',
    emergency_contact_name: u.emergency_contact_name ?? '',
    emergency_contact_phone: u.emergency_contact_phone ?? '',
    remarks: u.remarks ?? '',
    student_code: u.student_code ?? '',
    english_name: u.english_name ?? '',
    school_name: u.school_name ?? '',
    grade_class: u.grade_class ?? '',
    guardian1_name: u.guardian1_name ?? '',
    guardian1_relationship: u.guardian1_relationship ?? '',
    guardian1_phone: u.guardian1_phone ?? '',
    guardian2_name: u.guardian2_name ?? '',
    guardian2_relationship: u.guardian2_relationship ?? '',
    guardian2_phone: u.guardian2_phone ?? '',
    whatsapp_enabled: u.whatsapp_enabled,
  })
  dialogOpen.value = true
  nextTick(() => userFormRef.value?.resetValidation())
}

function normalizeString(value: string): string | null {
  const normalized = value.trim()

  return normalized.length > 0 ? normalized : null
}

function buildStudentPayload() {
  if (!isStudentRole.value) {
    return {
      student_code: null,
      english_name: null,
      school_name: null,
      grade_class: null,
      guardian1_name: null,
      guardian1_relationship: null,
      guardian1_phone: null,
      guardian2_name: null,
      guardian2_relationship: null,
      guardian2_phone: null,
      whatsapp_enabled: false,
    }
  }

  return {
    student_code: normalizeString(form.student_code),
    english_name: normalizeString(form.english_name),
    school_name: normalizeString(form.school_name),
    grade_class: normalizeString(form.grade_class),
    guardian1_name: normalizeString(form.guardian1_name),
    guardian1_relationship: normalizeString(form.guardian1_relationship),
    guardian1_phone: normalizeString(form.guardian1_phone),
    guardian2_name: normalizeString(form.guardian2_name),
    guardian2_relationship: normalizeString(form.guardian2_relationship),
    guardian2_phone: normalizeString(form.guardian2_phone),
    whatsapp_enabled: form.whatsapp_enabled,
  }
}

function formatAttendanceApiDetail(detail: unknown): string {
  if (detail == null)
    return ''
  if (typeof detail === 'string')
    return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object'))
      .map(entry => {
        const loc = entry.loc
        const msg = entry.msg
        const path = Array.isArray(loc) ? loc.filter((x): x is string => typeof x === 'string' && x !== 'body').join('.') : ''

        return path ? `${path}: ${msg}` : String(msg ?? 'Invalid value')
      })

    return parts.join(' · ')
  }

  return String(detail)
}

async function handleSave() {
  saveError.value = null

  const validation = await userFormRef.value?.validate()
  if (validation && !validation.valid)
    return

  saving.value = true
  try {
    const basePayload = {
      email: form.email.trim(),
      full_name: form.full_name.trim(),
      role: form.role,
      status: form.status,
      gender: normalizeString(form.gender),
      date_of_birth: normalizeString(form.date_of_birth),
      phone: normalizeString(form.phone),
      address: normalizeString(form.address),
      emergency_contact_name: normalizeString(form.emergency_contact_name),
      emergency_contact_phone: normalizeString(form.emergency_contact_phone),
      remarks: normalizeString(form.remarks),
      ...buildStudentPayload(),
    }

    if (editingUser.value) {
      await updateUser(editingUser.value.id, {
        ...basePayload,
        is_active: form.is_active,
      })
    }
    else {
      await createUser({
        ...basePayload,
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
      })
    }
    dialogOpen.value = false
    await loadUsers()
  }
  catch (e: unknown) {
    const data = e && typeof e === 'object' && 'data' in e ? (e as { data?: { detail?: unknown } }).data : undefined
    const msg = formatAttendanceApiDetail(data?.detail)

    saveError.value = msg || (e instanceof Error ? e.message : 'Could not save user')
  }
  finally {
    saving.value = false
  }
}

async function handleDelete(u: AttendanceUser) {
  if (!confirm(`Delete user ${u.username}?`))
    return

  await deleteUser(u.id)
  await loadUsers()
}

function roleColor(role: string) {
  if (role === 'admin')
    return 'error'

  if (role === 'staff')
    return 'info'

  return 'success'
}

function statusColor(status: string) {
  if (status === 'active')
    return 'success'

  if (status === 'suspended')
    return 'warning'

  return 'grey'
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
            <th>Phone</th>
            <th>School / Class</th>
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
              <VChip :color="statusColor(u.status)" size="small" label>
                {{ u.status }}
              </VChip>
            </td>
            <td>{{ u.phone || '-' }}</td>
            <td>{{ u.role === 'student' ? `${u.school_name || '-'} / ${u.grade_class || '-'}` : '-' }}</td>
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

    <VDialog v-model="dialogOpen" max-width="900" scrollable>
      <VCard>
        <VCardTitle class="text-h6 py-4">
          {{ editingUser ? 'Edit User' : 'Create User' }}
        </VCardTitle>
        <VDivider />
        <VCardText class="pa-4">
          <VAlert v-if="saveError" type="error" variant="tonal" density="compact" class="mb-4" closable @click:close="saveError = null">
            {{ saveError }}
          </VAlert>
          <VForm ref="userFormRef" @submit.prevent="handleSave">
            <VDefaultsProvider
              :defaults="{
                VTextField: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
                VSelect: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
                VTextarea: { density: 'compact', variant: 'outlined', hideDetails: 'auto' },
                VSwitch: { density: 'compact', hideDetails: true },
              }"
            >
              <h4 class="text-subtitle-2 text-medium-emphasis mb-2">
                Basic profile
              </h4>
              <VRow class="dense-form-row">
                <VCol cols="12" sm="6" md="4">
                  <VSelect v-model="form.status" :items="statusOptions" item-title="title" item-value="value" label="Status" />
                </VCol>
                <VCol cols="12" sm="6" md="4">
                  <VTextField
                    v-model="form.username"
                    label="Username / code *"
                    :disabled="!!editingUser"
                    required
                    maxlength="100"
                    :rules="usernameRules"
                  />
                </VCol>
                <VCol cols="12" sm="6" md="4">
                  <VSelect v-model="form.role" :items="['admin', 'staff', 'student']" label="Role" />
                </VCol>
                <VCol cols="12" sm="6">
                  <VTextField
                    v-model="form.full_name"
                    label="Full name *"
                    required
                    maxlength="255"
                    :rules="fullNameRules"
                  />
                </VCol>
                <VCol cols="12" sm="6">
                  <VTextField
                    v-model="form.english_name"
                    label="English name"
                    :disabled="!isStudentRole"
                    maxlength="255"
                    :rules="[maxCharsRule(255, 'English name')]"
                  />
                </VCol>
                <VCol cols="12" sm="6">
                  <VTextField
                    v-model="form.email"
                    label="Email *"
                    type="email"
                    autocomplete="email"
                    required
                    maxlength="255"
                    :rules="emailRules"
                  />
                </VCol>
                <VCol cols="12" sm="6">
                  <VTextField
                    v-if="!editingUser"
                    v-model="form.password"
                    label="Password *"
                    type="password"
                    autocomplete="new-password"
                    required
                    maxlength="128"
                    :rules="createPasswordRules"
                  />
                </VCol>
              </VRow>

              <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
                Contact & personal
              </h4>
              <VRow class="dense-form-row">
                <VCol cols="12" sm="6" md="4">
                  <VSelect v-model="form.gender" :items="genderOptions" item-title="title" item-value="value" label="Gender" clearable />
                </VCol>
                <VCol cols="12" sm="6" md="4">
                  <VTextField v-model="form.date_of_birth" label="Date of birth" type="date" />
                </VCol>
                <VCol cols="12" sm="6" md="4">
                  <VTextField
                    v-model="form.phone"
                    label="Phone"
                    maxlength="50"
                    :rules="[maxCharsRule(50, 'Phone')]"
                  />
                </VCol>
                <VCol cols="12">
                  <VTextField
                    v-model="form.address"
                    label="Address"
                    maxlength="500"
                    :rules="[maxCharsRule(500, 'Address')]"
                  />
                </VCol>
              </VRow>

              <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
                Emergency contact
              </h4>
              <VRow class="dense-form-row">
                <VCol cols="12" sm="6">
                  <VTextField
                    v-model="form.emergency_contact_name"
                    label="Emergency contact name"
                    maxlength="255"
                    :rules="[maxCharsRule(255, 'Emergency contact name')]"
                  />
                </VCol>
                <VCol cols="12" sm="6">
                  <VTextField
                    v-model="form.emergency_contact_phone"
                    label="Emergency contact phone"
                    maxlength="50"
                    :rules="[maxCharsRule(50, 'Emergency contact phone')]"
                  />
                </VCol>
              </VRow>

              <template v-if="isStudentRole">
                <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
                  Student details
                </h4>
                <VRow class="dense-form-row">
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.student_code"
                      label="Student code"
                      maxlength="100"
                      :rules="[maxCharsRule(100, 'Student code')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.school_name"
                      label="School name"
                      maxlength="255"
                      :rules="[maxCharsRule(255, 'School name')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.grade_class"
                      label="Grade / class"
                      maxlength="100"
                      :rules="[maxCharsRule(100, 'Grade / class')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.guardian1_name"
                      label="Guardian 1 name"
                      maxlength="255"
                      :rules="[maxCharsRule(255, 'Guardian 1 name')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VSelect v-model="form.guardian1_relationship" :items="relationshipOptions" label="Guardian 1 relationship" clearable />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.guardian1_phone"
                      label="Guardian 1 phone"
                      maxlength="50"
                      :rules="[maxCharsRule(50, 'Guardian 1 phone')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.guardian2_name"
                      label="Guardian 2 name"
                      maxlength="255"
                      :rules="[maxCharsRule(255, 'Guardian 2 name')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VSelect v-model="form.guardian2_relationship" :items="relationshipOptions" label="Guardian 2 relationship" clearable />
                  </VCol>
                  <VCol cols="12" sm="6" md="4">
                    <VTextField
                      v-model="form.guardian2_phone"
                      label="Guardian 2 phone"
                      maxlength="50"
                      :rules="[maxCharsRule(50, 'Guardian 2 phone')]"
                    />
                  </VCol>
                  <VCol cols="12" sm="6" md="4" class="d-flex align-center">
                    <VSwitch v-model="form.whatsapp_enabled" label="WhatsApp enabled" />
                  </VCol>
                </VRow>
              </template>

              <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
                Notes
              </h4>
              <VTextarea v-model="form.remarks" label="Remarks" rows="2" auto-grow class="mb-2" />

              <VSwitch
                v-if="editingUser"
                v-model="form.is_active"
                label="Login access enabled"
                class="mt-1"
              />
              <div class="d-flex justify-end gap-2 mt-4">
                <VBtn variant="text" density="compact" @click="dialogOpen = false">
                  Cancel
                </VBtn>
                <VBtn type="submit" color="primary" density="compact" size="small" :loading="saving">
                  Save
                </VBtn>
              </div>
            </VDefaultsProvider>
          </VForm>
        </VCardText>
      </VCard>
    </VDialog>
  </VContainer>
</template>

<style scoped lang="scss">
.dense-form-row :deep(.v-col) {
  padding-block: 4px !important;
}
</style>
