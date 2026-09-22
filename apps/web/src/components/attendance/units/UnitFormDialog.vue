<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import {
  maxCharsRule,
  requiredValidator,
} from '@core/utils/validators'
import {
  type CourseEnrollment,
  type CourseSku,
  listAllCourseEnrollments,
  listCourseSkus,
} from '@/api/attendance/courses'
import {
  type Unit,
  createUnit,
  updateStaffProfile,
  updateStudentProfile,
  updateUnit,
} from '@/api/attendance/units'
import {
  type UnitEnrollmentRow,
  billingUnitShortLabel,
  buildUnitEnrollmentRows,
  enrollmentStatusColor,
  formatEnrollmentRange,
} from '@/utils/courseEnrollmentDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import {
  type UnitFormState,
  buildUnitSavePayload,
  emptyUnitForm,
  unitSaveValidationError,
} from '@/utils/unitFormPayload'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  modelValue: boolean
  editingUnit: Unit | null
  locationOptions: { title: string; value: string }[]
  defaultLocationId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const { show: showToast } = useToast()

const open = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const form = reactive<UnitFormState>(emptyUnitForm())
const unitFormRef = ref<VForm>()
const saving = ref(false)
const saveError = ref<string | null>(null)

const unitEnrollmentRows = ref<UnitEnrollmentRow<CourseEnrollment, CourseSku>[]>([])
const unitEnrollmentsLoading = ref(false)
const unitEnrollmentsError = ref('')
let unitEnrollmentsRequestId = 0

const statusOptions = [
  { title: 'Active', value: 'active' },
  { title: 'Inactive', value: 'inactive' },
  { title: 'Suspended', value: 'suspended' },
]

const typeOptions = [
  { title: 'Student', value: 'student' },
  { title: 'Staff', value: 'staff' },
]

const employmentTypeOptions = [
  { title: 'Full-time', value: 'full_time' },
  { title: 'Part-time', value: 'part_time' },
]

const payTypeOptions = [
  { title: 'Hourly', value: 'hourly' },
  { title: 'Monthly', value: 'monthly' },
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

const codeRules = [requiredValidator, maxCharsRule(100, 'Code')] as const
const fullNameRules = [requiredValidator, maxCharsRule(255, 'Full name')] as const

watch(() => form.staff_profile.pay_type, payType => {
  if (payType === 'hourly') {
    form.staff_profile.monthly_salary = ''
  }
  else if (payType === 'monthly') {
    form.staff_profile.hourly_rate = ''
  }
  else {
    form.staff_profile.hourly_rate = ''
    form.staff_profile.monthly_salary = ''
  }
  if (payType && !form.staff_profile.ot_multiplier)
    form.staff_profile.ot_multiplier = '1.5'
})

watch(() => form.unit_type, type => {
  if (type !== 'staff') {
    form.staff_profile.employment_type = ''
    form.staff_profile.department = ''
    form.staff_profile.position = ''
    form.staff_profile.salary_grade = ''
    form.staff_profile.pay_type = ''
    form.staff_profile.hourly_rate = ''
    form.staff_profile.monthly_salary = ''
    form.staff_profile.ot_multiplier = ''
    form.staff_profile.work_schedule = ''
    form.staff_profile.supervisor_id = ''
    form.staff_profile.employment_notes = ''
  }
  if (type !== 'student') {
    form.student_profile.school_name = ''
    form.student_profile.grade_class = ''
    form.student_profile.student_id = ''
    form.student_profile.academic_notes = ''
    form.student_profile.guardians = {}
    form.guardians = [{ name: '', relationship: '', phone: '' }]
  }
})

watch(() => form.is_active, val => {
  form.status = val ? 'active' : 'inactive'
})

watch(() => form.status, val => {
  form.is_active = val !== 'inactive'
})

function resetForm() {
  Object.assign(form, emptyUnitForm({
    registered_location_id: props.defaultLocationId,
    scan_location_ids: props.defaultLocationId ? [props.defaultLocationId] : [],
  }))
}

function fillForm(unit: Unit) {
  const sp = unit.student_profile
  const stp = unit.staff_profile
  const guardians = sp?.guardians
    ? Object.values(sp.guardians).map(raw => {
      const g = (raw ?? {}) as { name?: unknown; relationship?: unknown; phone?: unknown }

      return {
        name: String(g.name ?? ''),
        relationship: String(g.relationship ?? ''),
        phone: String(g.phone ?? ''),
      }
    }).filter(g => g.name)
    : []

  Object.assign(form, {
    code: unit.code,
    full_name: unit.full_name,
    english_name: unit.english_name ?? '',
    unit_type: unit.unit_type,
    is_active: unit.is_active,
    status: unit.status ?? 'active',
    gender: unit.unit_type === 'staff' ? stp?.gender ?? '' : sp?.gender ?? '',
    date_of_birth: unit.unit_type === 'staff' ? stp?.date_of_birth ?? '' : sp?.date_of_birth ?? '',
    phone: unit.phone ?? '',
    address: unit.address ?? '',
    email: unit.email ?? '',
    emergency_contact_name: unit.emergency_contact_name ?? '',
    emergency_contact_phone: unit.emergency_contact_phone ?? '',
    photo_url: unit.photo_url ?? '',
    start_date: unit.start_date ?? '',
    exit_date: unit.exit_date ?? '',
    whatsapp_enabled: unit.whatsapp_enabled,
    remarks: unit.remarks ?? '',
    registered_location_id: unit.registered_location_id,
    scan_location_ids: [...unit.scan_location_ids],
    student_profile: {
      school_name: sp?.school_name ?? '',
      grade_class: sp?.grade_class ?? '',
      student_id: sp?.student_id ?? '',
      academic_notes: sp?.academic_notes ?? '',
      guardians: sp?.guardians ?? {},
    },
    guardians,
    staff_profile: {
      employee_id: stp?.employee_id ?? '',
      employment_type: stp?.employment_type === 'part_time' || stp?.employment_type === 'full_time'
        ? stp.employment_type
        : '',
      department: stp?.department ?? '',
      position: stp?.position ?? '',
      salary_grade: stp?.salary_grade ?? '',
      pay_type: stp?.pay_type === 'hourly' || stp?.pay_type === 'monthly' ? stp.pay_type : '',
      hourly_rate: stp?.hourly_rate != null ? String(stp.hourly_rate) : '',
      monthly_salary: stp?.monthly_salary != null ? String(stp.monthly_salary) : '',
      ot_multiplier: stp?.ot_multiplier != null ? String(stp.ot_multiplier) : '',
      work_schedule: stp?.work_schedule ?? '',
      supervisor_id: stp?.supervisor_id ?? '',
      employment_notes: stp?.employment_notes ?? '',
    },
  })
}

async function loadStudentEnrollments(unitId: string | null) {
  const requestId = ++unitEnrollmentsRequestId

  unitEnrollmentRows.value = []
  unitEnrollmentsError.value = ''
  if (!unitId) {
    unitEnrollmentsLoading.value = false

    return
  }

  unitEnrollmentsLoading.value = true
  try {
    const [enrollments, skuList] = await Promise.all([
      listAllCourseEnrollments({ unit_id: unitId }),
      listCourseSkus(),
    ])

    if (requestId !== unitEnrollmentsRequestId)
      return
    unitEnrollmentRows.value = buildUnitEnrollmentRows(enrollments, skuList)
  }
  catch (e) {
    if (requestId === unitEnrollmentsRequestId)
      unitEnrollmentsError.value = formatApiError(e, 'Could not load classes.')
  }
  finally {
    if (requestId === unitEnrollmentsRequestId)
      unitEnrollmentsLoading.value = false
  }
}

watch(open, value => {
  if (!value)
    return
  saveError.value = null
  if (props.editingUnit) {
    fillForm(props.editingUnit)
    void loadStudentEnrollments(props.editingUnit.unit_type === 'student' ? props.editingUnit.id : null)
  }
  else {
    resetForm()
    void loadStudentEnrollments(null)
  }
  nextTick(() => unitFormRef.value?.resetValidation())
})

async function handleSave() {
  saveError.value = unitSaveValidationError(form)
  if (saveError.value)
    return

  const validation = await unitFormRef.value?.validate()
  if (validation && !validation.valid)
    return

  saving.value = true
  try {
    const payload = buildUnitSavePayload(form)

    if (props.editingUnit) {
      await updateUnit(props.editingUnit.id, payload)

      if (form.unit_type === 'staff' && payload.staff_profile)
        await updateStaffProfile(props.editingUnit.id, payload.staff_profile)
      else if (form.unit_type === 'student' && payload.student_profile)
        await updateStudentProfile(props.editingUnit.id, payload.student_profile)
    }
    else {
      await createUnit(payload)
    }

    open.value = false
    emit('saved')
    showToast(props.editingUnit ? 'Unit updated successfully.' : 'Unit created successfully.', 'success')
  }
  catch (e: unknown) {
    saveError.value = formatApiError(e, 'Could not save unit')
    showToast(saveError.value, 'error')
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <AttendanceFormDialog
    v-model="open"
    :title="editingUnit ? 'Edit Unit' : 'Create Unit'"
    icon="ri-group-line"
    :max-width="900"
    :saving="saving"
    :error="saveError"
    @save="handleSave"
    @cancel="open = false"
    @clear-error="saveError = null"
  >
    <VForm
      ref="unitFormRef"
      @submit.prevent="handleSave"
    >
      <h4 class="text-subtitle-2 text-medium-emphasis mb-2">
        Basic info
      </h4>
      <VRow class="dense-form-row">
        <VCol
          cols="12"
          sm="6"
          md="4"
        >
          <VTextField
            v-model="form.code"
            label="Code *"
            :disabled="!!editingUnit"
            maxlength="100"
            :rules="codeRules"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="4"
        >
          <VSelect
            v-model="form.unit_type"
            :items="typeOptions"
            item-title="title"
            item-value="value"
            label="Type *"
            :disabled="!!editingUnit"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="4"
        >
          <VSelect
            v-model="form.status"
            :items="statusOptions"
            item-title="title"
            item-value="value"
            label="Status"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            v-model="form.full_name"
            label="Full name *"
            maxlength="255"
            :rules="fullNameRules"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            v-model="form.english_name"
            label="English name"
            maxlength="255"
            :rules="[maxCharsRule(255, 'English name')]"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            v-model="form.email"
            label="Email"
            maxlength="255"
            :rules="[maxCharsRule(255, 'Email')]"
          />
        </VCol>
      </VRow>

      <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
        Locations
      </h4>
      <VRow class="dense-form-row">
        <VCol
          cols="12"
          sm="6"
        >
          <VSelect
            v-model="form.registered_location_id"
            :items="locationOptions"
            item-title="title"
            item-value="value"
            label="Registered location *"
            :rules="[v => !!v || 'Required']"
            :disabled="locationOptions.length === 0"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VSelect
            v-model="form.scan_location_ids"
            :items="locationOptions"
            item-title="title"
            item-value="value"
            label="Scan locations *"
            hint="Check-in and check-out at these locations"
            multiple
            chips
            closable-chips
            :rules="[v => Array.isArray(v) && v.length > 0 || 'Select at least one']"
            :disabled="locationOptions.length === 0"
          />
        </VCol>
      </VRow>
      <p
        v-if="locationOptions.length === 0"
        class="text-caption text-warning mb-0"
      >
        No active locations found. Create locations first.
      </p>

      <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
        Contact & personal
      </h4>
      <VRow class="dense-form-row">
        <VCol
          cols="12"
          sm="6"
          md="4"
        >
          <VSelect
            v-model="form.gender"
            :items="genderOptions"
            item-title="title"
            item-value="value"
            label="Gender"
            clearable
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="4"
        >
          <VTextField
            v-model="form.date_of_birth"
            label="Date of birth"
            type="date"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="4"
        >
          <VTextField
            v-model="form.phone"
            label="Phone"
            maxlength="50"
            :rules="[maxCharsRule(50, 'Phone')]"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="4"
          class="d-flex align-center"
        >
          <VSwitch
            v-model="form.whatsapp_enabled"
            label="WhatsApp enabled"
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
        Additional info
      </h4>
      <VRow class="dense-form-row">
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            v-model="form.photo_url"
            label="Photo URL"
            maxlength="500"
            :rules="[maxCharsRule(500, 'Photo URL')]"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="3"
        >
          <VTextField
            v-model="form.start_date"
            label="Start date"
            type="date"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
          md="3"
        >
          <VTextField
            v-model="form.exit_date"
            label="Exit date"
            type="date"
          />
        </VCol>
      </VRow>

      <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
        Emergency contact
      </h4>
      <VRow class="dense-form-row">
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            v-model="form.emergency_contact_name"
            label="Emergency contact name"
            maxlength="255"
          />
        </VCol>
        <VCol
          cols="12"
          sm="6"
        >
          <VTextField
            v-model="form.emergency_contact_phone"
            label="Emergency contact phone"
            maxlength="50"
          />
        </VCol>
      </VRow>

      <template v-if="form.unit_type === 'student'">
        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          School & guardian
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.student_profile.school_name"
              label="School name"
              maxlength="255"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.student_profile.grade_class"
              label="Grade / class"
              maxlength="100"
            />
          </VCol>
          <template
            v-for="(g, idx) in form.guardians"
            :key="idx"
          >
            <VCol cols="12">
              <div class="d-flex align-center">
                <span class="text-caption text-medium-emphasis me-2">Guardian {{ idx + 1 }}</span>
                <VBtn
                  icon
                  size="x-small"
                  variant="text"
                  color="error"
                  :disabled="form.guardians.length <= 1"
                  @click="form.guardians.splice(idx, 1)"
                >
                  <VIcon>ri-delete-bin-line</VIcon>
                </VBtn>
              </div>
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="g.name"
                label="Name"
                maxlength="255"
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VSelect
                v-model="g.relationship"
                :items="relationshipOptions"
                label="Relationship"
                clearable
              />
            </VCol>
            <VCol
              cols="12"
              sm="6"
              md="4"
            >
              <VTextField
                v-model="g.phone"
                label="Phone"
                maxlength="50"
              />
            </VCol>
          </template>
          <VCol cols="12">
            <VBtn
              size="small"
              variant="text"
              prepend-icon="ri-add-line"
              @click="form.guardians.push({ name: '', relationship: '', phone: '' })"
            >
              Add guardian
            </VBtn>
          </VCol>
        </VRow>
      </template>

      <template v-if="form.unit_type === 'student'">
        <h4 class="text-subtitle-2 text-medium-emphasis mb-1 mt-4">
          Classes
        </h4>
        <p class="text-caption text-medium-emphasis mb-2">
          Read-only. Join, change dates, or Leave class on Courses.
        </p>
        <div
          v-if="!editingUnit"
          class="text-body-2 text-medium-emphasis"
        >
          Save this student first, then enroll from Courses.
        </div>
        <div
          v-else-if="unitEnrollmentsLoading"
          class="text-body-2 text-medium-emphasis"
        >
          Loading classes…
        </div>
        <p
          v-else-if="unitEnrollmentsError"
          class="text-caption text-error mb-0"
        >
          {{ unitEnrollmentsError }}
        </p>
        <div
          v-else-if="unitEnrollmentRows.length === 0"
          class="d-flex align-center flex-wrap ga-2"
        >
          <span class="text-body-2 text-medium-emphasis">Not enrolled in any class.</span>
          <VBtn
            type="button"
            size="small"
            variant="text"
            color="primary"
            :to="{ name: 'attendance-courses' }"
          >
            Open Courses
          </VBtn>
        </div>
        <div
          v-else
          class="unit-enrollment-list"
        >
          <div
            v-for="row in unitEnrollmentRows"
            :key="row.enrollment.id"
            class="unit-enrollment-row"
          >
            <div class="unit-enrollment-copy">
              <div class="d-flex align-center flex-wrap ga-2">
                <span class="font-weight-medium">{{ row.sku?.name_zh ?? 'Unknown class' }}</span>
                <VChip
                  size="x-small"
                  :color="enrollmentStatusColor[row.enrollment.status] ?? 'grey'"
                >
                  {{ row.enrollment.status }}
                </VChip>
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ row.sku ? `${row.sku.code} · ${billingUnitShortLabel(row.sku.billing_unit)}` : row.enrollment.sku_id }}
                · {{ formatEnrollmentRange(row.enrollment.start_date, row.enrollment.end_date) }}
              </div>
            </div>
            <VBtn
              v-if="row.sku"
              type="button"
              size="small"
              variant="text"
              color="primary"
              append-icon="ri-arrow-right-s-line"
              :to="{ name: 'attendance-courses', query: { sku: row.sku.id } }"
            >
              Roster
            </VBtn>
          </div>
        </div>
      </template>

      <template v-if="form.unit_type === 'staff'">
        <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
          Staff profile
        </h4>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VSelect
              v-model="form.staff_profile.employment_type"
              :items="employmentTypeOptions"
              item-title="title"
              item-value="value"
              label="Employment type *"
              :rules="[v => !!v || 'Required for staff']"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.staff_profile.employee_id"
              label="Employee ID"
              maxlength="100"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.staff_profile.department"
              label="Department"
              maxlength="100"
            />
          </VCol>
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.staff_profile.position"
              label="Position"
              maxlength="100"
            />
          </VCol>
        </VRow>

        <h5 class="text-caption text-medium-emphasis mb-2 mt-4">
          Compensation
        </h5>
        <VRow class="dense-form-row">
          <VCol
            cols="12"
            sm="6"
            md="4"
          >
            <VSelect
              v-model="form.staff_profile.pay_type"
              :items="payTypeOptions"
              item-title="title"
              item-value="value"
              label="Pay type *"
              clearable
              :rules="[v => !!v || 'Required for staff']"
            />
          </VCol>
          <VCol
            v-if="form.staff_profile.pay_type === 'hourly'"
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.staff_profile.hourly_rate"
              label="Hourly rate"
              type="number"
              min="0"
              step="0.01"
            />
          </VCol>
          <VCol
            v-if="form.staff_profile.pay_type === 'monthly'"
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.staff_profile.monthly_salary"
              label="Monthly salary"
              type="number"
              min="0"
              step="0.01"
            />
          </VCol>
          <VCol
            v-if="form.staff_profile.pay_type"
            cols="12"
            sm="6"
            md="4"
          >
            <VTextField
              v-model="form.staff_profile.ot_multiplier"
              label="OT multiplier"
              type="number"
              min="0"
              step="0.01"
              hint="Defaults to 1.5x when left blank"
              persistent-hint
            />
          </VCol>
        </VRow>
      </template>

      <h4 class="text-subtitle-2 text-medium-emphasis mb-2 mt-4">
        Notes
      </h4>
      <VTextarea
        v-model="form.remarks"
        label="Remarks"
        rows="2"
        auto-grow
        class="mb-2"
      />

      <VSwitch
        v-model="form.is_active"
        label="Active (can scan QR and appear in attendance)"
        class="mt-1"
      />
    </VForm>
  </AttendanceFormDialog>
</template>

<style scoped lang="scss">
.dense-form-row :deep(.v-col) {
  padding-block: 4px !important;
}

.unit-enrollment-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.unit-enrollment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
}

.unit-enrollment-copy {
  min-width: 0;
}
</style>
