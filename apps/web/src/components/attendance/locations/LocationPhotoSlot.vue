<script setup lang="ts">
import { uploadMedia } from '@/api/attendance/uploads'
import { useToast } from '@/composables/useToast'
import { formatApiError } from '@/utils/formatApiDetail'
import { resolveMediaUrl } from '@/utils/mediaUrl'

const url = defineModel<string>('url', { required: true })
const previewError = defineModel<boolean>('previewError', { required: true })

const props = withDefaults(defineProps<{
  title: string
  hint?: string
  previewMaxHeight?: number
}>(), {
  hint: '',
  previewMaxHeight: 160,
})

const { show: showToast } = useToast()
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const showUrlField = ref(false)

const previewSrc = computed(() => resolveMediaUrl(url.value))

function openPicker() {
  fileInput.value?.click()
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  input.value = ''
  if (!file)
    return

  if (!file.type.startsWith('image/')) {
    showToast('Please choose a JPEG, PNG, WebP, or GIF image', 'error')

    return
  }

  uploading.value = true
  try {
    const result = await uploadMedia(file)

    url.value = result.url
    previewError.value = false
  }
  catch (error) {
    showToast(formatApiError(error, 'Upload failed'), 'error')
  }
  finally {
    uploading.value = false
  }
}

function clearPhoto() {
  url.value = ''
  previewError.value = false
}
</script>

<template>
  <div>
    <div class="text-subtitle-2 mb-2">
      {{ props.title }}
      <span
        v-if="props.hint"
        class="text-caption text-medium-emphasis ml-1"
      >— {{ props.hint }}</span>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/webp,image/gif"
      class="d-none"
      @change="onFileChange"
    >

    <div
      class="photo-slot rounded-lg border"
      :class="{ 'photo-slot--empty': !url.trim() }"
    >
      <div
        v-if="url.trim() && !previewError"
        class="photo-slot__preview"
      >
        <VImg
          :src="previewSrc"
          :max-height="props.previewMaxHeight"
          class="photo-slot__img"
          @error="previewError = true"
        />
      </div>
      <div
        v-else-if="url.trim() && previewError"
        class="text-caption text-error pa-3"
      >
        <VIcon
          icon="ri-error-warning-line"
          size="14"
          class="me-1"
        />Cannot load image
      </div>
      <button
        v-else
        type="button"
        class="photo-slot__drop"
        :disabled="uploading"
        @click="openPicker"
      >
        <VIcon
          icon="ri-upload-2-line"
          size="22"
          class="mb-1"
        />
        <span class="text-body-2">Click to upload</span>
        <span class="text-caption text-medium-emphasis">JPEG, PNG, WebP, GIF</span>
      </button>

      <div
        v-if="uploading"
        class="photo-slot__busy"
      >
        <VProgressCircular
          indeterminate
          size="28"
          width="3"
        />
      </div>
    </div>

    <div class="d-flex flex-wrap align-center gap-1 mt-2">
      <VBtn
        size="small"
        variant="tonal"
        prepend-icon="ri-upload-2-line"
        :loading="uploading"
        @click="openPicker"
      >
        {{ url.trim() ? 'Replace' : 'Upload' }}
      </VBtn>
      <VBtn
        v-if="url.trim()"
        size="small"
        variant="text"
        color="error"
        prepend-icon="ri-delete-bin-line"
        :disabled="uploading"
        @click="clearPhoto"
      >
        Remove
      </VBtn>
      <VBtn
        size="small"
        variant="text"
        :prepend-icon="showUrlField ? 'ri-arrow-up-s-line' : 'ri-link'"
        @click="showUrlField = !showUrlField"
      >
        {{ showUrlField ? 'Hide URL' : 'Paste URL' }}
      </VBtn>
    </div>

    <VTextField
      v-if="showUrlField"
      v-model="url"
      class="mt-2"
      placeholder="https://… or /api/uploads/…"
      density="compact"
      hide-details
      @update:model-value="previewError = false"
    />
  </div>
</template>

<style scoped>
.photo-slot {
  position: relative;
  overflow: hidden;
  min-height: 88px;
}

.photo-slot--empty {
  border-style: dashed;
}

.photo-slot__preview {
  display: flex;
  justify-content: flex-start;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.photo-slot__img {
  width: auto;
  max-width: 100%;
}

.photo-slot__drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 100%;
  min-height: 96px;
  padding: 16px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.photo-slot__drop:disabled {
  opacity: 0.6;
  cursor: wait;
}

.photo-slot__busy {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-surface), 0.72);
}
</style>
