<script setup lang="ts">
import AttendanceConfirmDialog from '@/components/attendance/AttendanceConfirmDialog.vue'
import { useGlobalConfirm } from '@/composables/useGlobalConfirm'

const { state, resolve } = useGlobalConfirm()

// If the dialog is closed without an answer, resolve as cancelled.
watch(() => state.open, open => {
  if (!open)
    resolve(false)
})
</script>

<template>
  <AttendanceConfirmDialog
    v-model="state.open"
    :title="state.title"
    :confirm-label="state.confirmLabel"
    :cancel-label="state.cancelLabel"
    :tone="state.tone"
    :details="state.details"
    @confirm="resolve(true)"
    @cancel="resolve(false)"
  >
    {{ state.message }}
  </AttendanceConfirmDialog>
</template>
