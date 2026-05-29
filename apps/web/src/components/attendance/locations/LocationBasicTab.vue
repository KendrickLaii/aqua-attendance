<script setup lang="ts">
import type { DaySchedule } from '@/utils/locationHours'

export interface LocationBasicForm {
  code: string
  name_zh: string
  name_en: string
  location_type: string
  region: string
  is_active: boolean
}

defineProps<{
  form: LocationBasicForm
  regionOptions: string[]
}>()

const hoursSchedule = defineModel<DaySchedule[]>('hoursSchedule', { required: true })
</script>

<template>
  <VRow class="mt-1">
    <VCol
      cols="12"
      sm="8"
    >
      <VTextField
        v-model="form.name_en"
        label="English Name *"
        prepend-inner-icon="ri-translate-2"
        :rules="[v => !!v.trim() || 'English name is required']"
        autofocus
      />
    </VCol>
    <VCol
      cols="12"
      sm="4"
    >
      <VTextField
        v-model="form.code"
        label="Code"
        prepend-inner-icon="ri-hashtag"
      />
    </VCol>
    <VCol
      cols="12"
      sm="8"
    >
      <VTextField
        v-model="form.name_zh"
        label="Chinese Name"
        hint="Optional — defaults to English name if left blank"
        persistent-hint
        prepend-inner-icon="ri-translate"
      />
    </VCol>
    <VCol
      cols="12"
      sm="4"
    >
      <VSwitch
        v-model="form.is_active"
        label="Active"
        inset
        color="success"
        hide-details
      />
    </VCol>
    <VCol
      cols="12"
      sm="6"
    >
      <VTextField
        v-model="form.location_type"
        label="Type"
        prepend-inner-icon="ri-store-2-line"
        placeholder="e.g. Classroom, Branch"
      />
    </VCol>
    <VCol
      cols="12"
      sm="6"
    >
      <VCombobox
        v-model="form.region"
        :items="regionOptions"
        label="Region / District"
        prepend-inner-icon="ri-map-2-line"
        clearable
        hint="Select existing or type a new region"
        persistent-hint
      />
    </VCol>
    <VCol cols="12">
      <LocationHoursEditor v-model="hoursSchedule" />
    </VCol>
  </VRow>
</template>
