<script setup lang="ts">
export interface LocationExtraForm {
  notes: string
  details_json: string
}

defineProps<{
  form: LocationExtraForm
}>()
</script>

<template>
  <VRow class="mt-1">
    <VCol cols="12">
      <VTextarea
        v-model="form.notes"
        label="Notes"
        rows="3"
        prepend-inner-icon="ri-sticky-note-line"
      />
    </VCol>
    <VCol cols="12">
      <VTextarea
        v-model="form.details_json"
        label="Extra Details (JSON)"
        rows="4"
        hint='Free-form key/value pairs. Example: {"floor":"2F","room":"A-01"}'
        persistent-hint
        prepend-inner-icon="ri-code-line"
        :rules="[v => { if (!v.trim()) return true; try { JSON.parse(v); return true } catch { return 'Invalid JSON' } }]"
      />
    </VCol>
  </VRow>
</template>
