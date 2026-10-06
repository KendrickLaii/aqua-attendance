<script setup lang="ts">
import { type DetailPhotoRow, addDetailPhotoRow, removeDetailPhotoRow } from '@/utils/locationPhotos'
import LocationPhotoSlot from '@/components/attendance/locations/LocationPhotoSlot.vue'

const MAX_DETAIL_PHOTOS = 10

const iconUrl = defineModel<string>('iconUrl', { required: true })
const mainPhotoUrl = defineModel<string>('mainPhotoUrl', { required: true })
const detailPhotoRows = defineModel<DetailPhotoRow[]>('detailPhotoRows', { required: true })
const iconPreviewError = defineModel<boolean>('iconPreviewError', { required: true })
const mainPreviewError = defineModel<boolean>('mainPreviewError', { required: true })
</script>

<template>
  <VRow class="mt-1">
    <VCol cols="12">
      <LocationPhotoSlot
        v-model:url="iconUrl"
        v-model:preview-error="iconPreviewError"
        title="Icon"
        hint="small image for lists"
        :preview-max-height="100"
      />
    </VCol>

    <VCol cols="12">
      <VDivider class="mb-3" />
      <LocationPhotoSlot
        v-model:url="mainPhotoUrl"
        v-model:preview-error="mainPreviewError"
        title="Main photo"
        hint="cover / hero image"
        :preview-max-height="200"
      />
    </VCol>

    <VCol cols="12">
      <VDivider class="mb-3" />
      <div class="text-subtitle-2 mb-2">
        <VIcon
          icon="ri-gallery-line"
          size="16"
          class="me-1"
        />Detail photos
        <span class="text-caption text-medium-emphasis ms-1">— gallery / additional images</span>
      </div>
      <div
        v-for="(row, index) in detailPhotoRows"
        :key="index"
        class="mb-3"
      >
        <VCard
          variant="outlined"
          class="pa-3"
        >
          <LocationPhotoSlot
            v-model:url="row.url"
            v-model:preview-error="row.previewError"
            :title="`Photo ${index + 1}`"
            :preview-max-height="120"
          />
          <VTextField
            v-model="row.caption"
            class="mt-3"
            label="Caption"
            density="compact"
            hide-details
          />
          <div class="d-flex justify-end mt-2">
            <VBtn
              size="small"
              variant="text"
              color="error"
              prepend-icon="ri-delete-bin-line"
              @click="removeDetailPhotoRow(detailPhotoRows, index)"
            >
              Remove photo
            </VBtn>
          </div>
        </VCard>
      </div>
      <VBtn
        size="small"
        variant="tonal"
        prepend-icon="ri-add-line"
        :disabled="detailPhotoRows.length >= MAX_DETAIL_PHOTOS"
        @click="addDetailPhotoRow(detailPhotoRows)"
      >
        Add photo
      </VBtn>
      <span class="text-caption text-medium-emphasis ms-2">{{ detailPhotoRows.length }}/{{ MAX_DETAIL_PHOTOS }}</span>
    </VCol>
  </VRow>
</template>
