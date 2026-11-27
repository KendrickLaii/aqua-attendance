<script setup lang="ts">
import type { VForm } from 'vuetify/components/VForm'
import { attendanceCreatePasswordValidator, requiredValidator } from '@core/utils/validators'
import { attendanceChangePassword } from '@/api/attendance/auth'
import { formatApiError } from '@/utils/formatApiDetail'

const open = defineModel<boolean>({ required: true })

const formRef = ref<VForm>()
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const showCurrent = ref(false)
const showNew = ref(false)
const busy = ref(false)
const error = ref('')
const saved = ref(false)

const confirmRule = (value: string) => value === newPassword.value || 'The two new passwords do not match'

watch(open, value => {
  if (!value)
    return
  currentPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  error.value = ''
  saved.value = false
  formRef.value?.resetValidation()
})

async function submit() {
  const result = await formRef.value?.validate()
  if (!result?.valid)
    return
  busy.value = true
  error.value = ''
  try {
    await attendanceChangePassword(currentPassword.value, newPassword.value)
    saved.value = true
    open.value = false
  }
  catch (e) {
    error.value = formatApiError(e, 'Could not change the password.')
  }
  finally {
    busy.value = false
  }
}
</script>

<template>
  <VDialog
    v-model="open"
    max-width="440"
  >
    <VCard>
      <VCardTitle>Change password</VCardTitle>
      <VCardText>
        <VAlert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          class="mb-3"
        >
          {{ error }}
        </VAlert>
        <VForm
          ref="formRef"
          @submit.prevent="submit"
        >
          <VTextField
            v-model="currentPassword"
            label="Current password"
            :type="showCurrent ? 'text' : 'password'"
            autocomplete="current-password"
            :rules="[requiredValidator]"
            class="mb-2"
          >
            <template #append-inner>
              <VIcon
                :icon="showCurrent ? 'ri-eye-off-line' : 'ri-eye-line'"
                class="cursor-pointer"
                @click="showCurrent = !showCurrent"
              />
            </template>
          </VTextField>
          <VTextField
            v-model="newPassword"
            label="New password"
            :type="showNew ? 'text' : 'password'"
            autocomplete="new-password"
            :rules="[requiredValidator, attendanceCreatePasswordValidator]"
            hint="At least 6 characters"
            persistent-hint
            class="mb-2"
          >
            <template #append-inner>
              <VIcon
                :icon="showNew ? 'ri-eye-off-line' : 'ri-eye-line'"
                class="cursor-pointer"
                @click="showNew = !showNew"
              />
            </template>
          </VTextField>
          <VTextField
            v-model="confirmPassword"
            label="Confirm new password"
            type="password"
            autocomplete="new-password"
            :rules="[requiredValidator, confirmRule]"
          />
        </VForm>
      </VCardText>
      <VCardActions>
        <VSpacer />
        <VBtn
          variant="text"
          @click="open = false"
        >
          Cancel
        </VBtn>
        <VBtn
          color="primary"
          :loading="busy"
          @click="submit"
        >
          Save
        </VBtn>
      </VCardActions>
    </VCard>
  </VDialog>
  <VSnackbar
    v-model="saved"
    color="success"
    timeout="3000"
  >
    Password changed.
  </VSnackbar>
</template>
