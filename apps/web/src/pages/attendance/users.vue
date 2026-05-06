<script setup lang="ts">
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { createUser, deleteUser, listUsers, updateUser } from '@/api/attendance/users'
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
}

function openEdit(u: AttendanceUser) {
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

async function handleSave() {
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
        username: form.username,
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
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

    <VDialog v-model="dialogOpen" max-width="1100">
      <VCard>
        <VCardTitle>{{ editingUser ? 'Edit User' : 'Create User' }}</VCardTitle>
        <VCardText>
          <VForm @submit.prevent="handleSave">
            <h4 class="text-subtitle-1 mb-3">Basic Profile</h4>
            <VRow>
              <VCol cols="12" md="4">
                <VSelect v-model="form.status" :items="statusOptions" item-title="title" item-value="value" label="Status" />
              </VCol>
              <VCol cols="12" md="4">
                <VTextField v-model="form.username" label="Username / Code" :disabled="!!editingUser" required />
              </VCol>
              <VCol cols="12" md="4">
                <VSelect v-model="form.role" :items="['admin', 'staff', 'student']" label="Role" />
              </VCol>
              <VCol cols="12" md="6">
                <VTextField v-model="form.full_name" label="Full Name" required />
              </VCol>
              <VCol cols="12" md="6">
                <VTextField v-model="form.english_name" label="English Name" :disabled="!isStudentRole" />
              </VCol>
              <VCol cols="12" md="6">
                <VTextField v-model="form.email" label="Email" type="email" required />
              </VCol>
              <VCol cols="12" md="6">
                <VTextField
                  v-if="!editingUser"
                  v-model="form.password"
                  label="Password"
                  type="password"
                  required
                />
              </VCol>
            </VRow>

            <h4 class="text-subtitle-1 mt-4 mb-3">Contact & Personal</h4>
            <VRow>
              <VCol cols="12" md="4">
                <VSelect v-model="form.gender" :items="genderOptions" item-title="title" item-value="value" label="Gender" />
              </VCol>
              <VCol cols="12" md="4">
                <VTextField v-model="form.date_of_birth" label="Date of Birth" type="date" />
              </VCol>
              <VCol cols="12" md="4">
                <VTextField v-model="form.phone" label="Phone" />
              </VCol>
              <VCol cols="12">
                <VTextField v-model="form.address" label="Address" />
              </VCol>
            </VRow>

            <h4 class="text-subtitle-1 mt-4 mb-3">Emergency Contact</h4>
            <VRow>
              <VCol cols="12" md="6">
                <VTextField v-model="form.emergency_contact_name" label="Emergency Contact Name" />
              </VCol>
              <VCol cols="12" md="6">
                <VTextField v-model="form.emergency_contact_phone" label="Emergency Contact Phone" />
              </VCol>
            </VRow>

            <template v-if="isStudentRole">
              <h4 class="text-subtitle-1 mt-4 mb-3">Student Details</h4>
              <VRow>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.student_code" label="Student Code" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.school_name" label="School Name" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.grade_class" label="Grade / Class" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.guardian1_name" label="Guardian 1 Name" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSelect v-model="form.guardian1_relationship" :items="relationshipOptions" label="Guardian 1 Relationship" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.guardian1_phone" label="Guardian 1 Phone" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.guardian2_name" label="Guardian 2 Name" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSelect v-model="form.guardian2_relationship" :items="relationshipOptions" label="Guardian 2 Relationship" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.guardian2_phone" label="Guardian 2 Phone" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.whatsapp_enabled" label="WhatsApp Enabled" />
                </VCol>
              </VRow>
            </template>

            <h4 class="text-subtitle-1 mt-4 mb-3">Notes</h4>
            <VTextarea v-model="form.remarks" label="Remarks" rows="3" class="mb-3" />

            <VSwitch
              v-if="editingUser"
              v-model="form.is_active"
              label="Login Access Enabled"
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
