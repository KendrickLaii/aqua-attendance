<script setup lang="ts">
import { addDetailPhotoRow, removeDetailPhotoRow, type DetailPhotoRow } from '@/utils/locationPhotos'

export interface LocationPhotosForm {
  icon_url: string
  main_photo_url: string
}

defineProps<{
  form: LocationPhotosForm
}>()

const detailPhotoRows = defineModel<DetailPhotoRow[]>('detailPhotoRows', { required: true })
const iconPreviewError = defineModel<boolean>('iconPreviewError', { required: true })
const mainPreviewError = defineModel<boolean>('mainPreviewError', { required: true })
</script>

<template>
  <VRow class="mt-1">
    <VCol cols="12">
      <div class="text-subtitle-2 mb-2">
        <VIcon
          icon="ri-image-circle-line"
          size="16"
          class="me-1"
        />Icon URL
        <span class="text-caption text-medium-emphasis ml-1">— small image for lists</span>
      </div>
      <VTextField
        v-model="form.icon_url"
        placeholder="https://..."
        density="compact"
        @update:model-value="iconPreviewError = false"
      />
      <div
        v-if="form.icon_url.trim()"
        class="mt-2 mb-3"
      >
        <VImg
          v-if="!iconPreviewError"
          :src="form.icon_url.trim()"
          max-height="100"
          max-width="100"
          rounded="lg"
          class="border"
          @error="iconPreviewError = true"
        />
        <div
          v-else
          class="text-caption text-error"
        >
          <VIcon
            icon="ri-error-warning-line"
            size="14"
            class="me-1"
          />Cannot load image
        </div>
      </div>
    </VCol>

    <VCol cols="12">
      <VDivider class="mb-3" />
      <div class="text-subtitle-2 mb-2">
        <VIcon
          icon="ri-image-2-line"
          size="16"
          class="me-1"
        />Main Photo URL
        <span class="text-caption text-medium-emphasis ml-1">— cover / hero image</span>
      </div>
      <VTextField
        v-model="form.main_photo_url"
        placeholder="https://..."
        density="compact"
        @update:model-value="mainPreviewError = false"
      />
      <div
        v-if="form.main_photo_url.trim()"
        class="mt-2 mb-3"
      >
        <VImg
          v-if="!mainPreviewError"
          :src="form.main_photo_url.trim()"
          max-height="200"
          rounded="lg"
          class="border"
          @error="mainPreviewError = true"
        />
        <div
          v-else
          class="text-caption text-error"
        >
          <VIcon
            icon="ri-error-warning-line"
            size="14"
            class="me-1"
          />Cannot load image
        </div>
      </div>
    </VCol>

    <VCol cols="12">
      <VDivider class="mb-3" />
      <div class="text-subtitle-2 mb-2">
        <VIcon
          icon="ri-gallery-line"
          size="16"
          class="me-1"
        />Detail Photos
        <span class="text-caption text-medium-emphasis ml-1">— gallery / additional images</span>
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
          <VRow
            dense
            align="center"
          >
            <VCol
              cols="12"
              sm="7"
            >
              <VTextField
                v-model="row.url"
                label="Photo URL"
                density="compact"
                hide-details
                placeholder="https://..."
                @update:model-value="row.previewError = false"
              />
            </VCol>
            <VCol
              cols="12"
              sm="4"
            >
              <VTextField
                v-model="row.caption"
                label="Caption"
                density="compact"
                hide-details
              />
            </VCol>
            <VCol cols="auto">
              <VBtn
                icon
                size="small"
                variant="text"
                color="error"
                @click="removeDetailPhotoRow(detailPhotoRows, index)"
              >
                <VIcon icon="ri-delete-bin-line" />
              </VBtn>
            </VCol>
          </VRow>
          <div
            v-if="row.url.trim()"
            class="mt-2"
          >
            <VImg
              v-if="!row.previewError"
              :src="row.url.trim()"
              max-height="120"
              max-width="180"
              rounded="md"
              class="border"
              @error="row.previewError = true"
            />
            <div
              v-else
              class="text-caption text-error"
            >
              <VIcon
                icon="ri-error-warning-line"
                size="14"
                class="me-1"
              />Cannot load image
            </div>
          </div>
        </VCard>
      </div>
      <VBtn
        size="small"
        variant="tonal"
        prepend-icon="ri-add-line"
        @click="addDetailPhotoRow(detailPhotoRows)"
      >
        Add photo
      </VBtn>
    </VCol>
  </VRow>
</template>
