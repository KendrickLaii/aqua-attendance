<script setup lang="ts">
import type { TaxAttachmentListItem } from '@/types/attachment'
import { useToast } from '@/composables/useToast'
import { useDropZone, useFileDialog, useObjectUrl } from '@vueuse/core'
import excelPreviewImage from '@/assets/images/aqua/preview-image/excel.png'
import pdfPreviewImage from '@/assets/images/aqua/preview-image/pdf.png'
import wordPreviewImage from '@/assets/images/aqua/preview-image/word.png'
import zipPreviewImage from '@/assets/images/aqua/preview-image/zip.png'

const dropZoneRef = ref<HTMLDivElement>()
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
const { show: showToast } = useToast()

const items = defineModel<TaxAttachmentListItem[]>({ default: () => [] })

const { open, onChange } = useFileDialog()

function pushFile(file: File) {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    showToast(`File "${file.name}" exceeds 10MB limit.`, 'error')
    return
  }

  const url = useObjectUrl(file).value ?? ''
  items.value = [...items.value, {
    file,
    url,
    name: file.name,
    size: file.size,
  }]
}

function onDrop(DroppedFiles: File[] | null) {
  DroppedFiles?.forEach(file => pushFile(file))
}

onChange((selectedFiles: FileList | null | undefined) => {
  if (!selectedFiles)
    return

  for (const file of selectedFiles)
    pushFile(file)
})

useDropZone(dropZoneRef, onDrop)

function removeAt(index: number) {
  const item = items.value[index]
  if (item?.file && item.url.startsWith('blob:'))
    URL.revokeObjectURL(item.url)
  items.value = items.value.filter((_, i) => i !== index)
}

function downloadAt(index: number) {
  const item = items.value[index]
  if (!item?.url) return

  const link = document.createElement('a')
  link.href = item.url
  link.download = item.name || `attachment-${index + 1}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function isImageItem(item: TaxAttachmentListItem): boolean {
  const fileType = item.file?.type ?? ''
  if (fileType.startsWith('image/'))
    return true

  const name = String(item.name ?? '').toLowerCase()
  return /\.(png|jpe?g|gif|webp|ico|bmp|svg)$/.test(name)
}

function isPdfItem(item: TaxAttachmentListItem): boolean {
  const fileType = item.file?.type ?? ''
  if (fileType === 'application/pdf')
    return true

  const name = String(item.name ?? '').toLowerCase()
  return /\.pdf$/.test(name)
}

function isExcelItem(item: TaxAttachmentListItem): boolean {
  const fileType = item.file?.type ?? ''
  if (fileType === 'application/vnd.ms-excel' || fileType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return true

  const name = String(item.name ?? '').toLowerCase()
  return /\.(xls|xlsx|xlsm|csv)$/.test(name)
}

function isWordItem(item: TaxAttachmentListItem): boolean {
  const fileType = item.file?.type ?? ''
  if (fileType
    === 'application/msword'
    || fileType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    || fileType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.template'
    || fileType === 'application/vnd.ms-word.document.macroEnabled.12'
  )
    return true

  const name = String(item.name ?? '').toLowerCase()
  return /\.(doc|docx|docm|dot|dotx|rtf)$/.test(name)
}

function isZipItem(item: TaxAttachmentListItem): boolean {
  const fileType = item.file?.type ?? ''
  if (fileType === 'application/zip' || fileType === 'application/x-zip-compressed')
    return true

  const name = String(item.name ?? '').toLowerCase()
  return /\.(zip|rar|7z)$/.test(name)
}

function formatFileSize(size?: number): string {
  const bytes = Number(size ?? 0)
  if (!Number.isFinite(bytes) || bytes <= 0)
    return '0 KB'

  const oneMb = 1024 * 1024
  if (bytes < oneMb)
    return `${(bytes / 1024).toFixed(2)} KB`

  return `${(bytes / oneMb).toFixed(2)} MB`
}
</script>

<template>
  <div class="flex">
    <div class="w-full h-auto relative">
      <div
        ref="dropZoneRef"
        class="cursor-pointer"
        @click="() => open()"
      >
        <div
          v-if="items.length === 0"
          class="d-flex flex-column justify-center align-center gap-y-2 pa-12 file-upload-zone rounded"
        >
          <IconBtn
            variant="tonal"
            color="secondary"
            class="rounded"
            size="40"
          >
            <VIcon
              size="24"
              icon="ri-upload-2-line"
            />
          </IconBtn>
          <h4 class="text-h4">
            Drag and drop your file here.
          </h4>
          <span class="text-disabled">or</span>

          <VBtn
            variant="elevated"
            size="small"
            color="primary"
          >
            Browse Images
          </VBtn>
        </div>

        <div
          v-else
          class="d-flex justify-center align-center gap-3 pa-8 file-upload-zone flex-wrap"
        >
          <VRow class="match-height w-100">
            <template
              v-for="(item, index) in items"
              :key="`${item.url}-${index}`"
            >
              <VCol
                cols="12"
                sm="4"
                class="file-card-col"
              >
                <VCard :ripple="false" class="file-card">
                  <VCardText
                    class="d-flex flex-column file-card-content"
                    @click.stop
                  >
                    <VImg
                      v-if="isImageItem(item)"
                      :src="item.url"
                      class="w-100 mx-auto file-preview-image"
                    />
                    <VImg
                      v-else-if="isPdfItem(item)"
                      :src="pdfPreviewImage"
                      class="w-100 mx-auto file-preview-image"
                    />
                    <VImg
                      v-else-if="isExcelItem(item)"
                      :src="excelPreviewImage"
                      class="w-100 mx-auto file-preview-image"
                    />
                    <VImg
                      v-else-if="isWordItem(item)"
                      :src="wordPreviewImage"
                      class="w-100 mx-auto file-preview-image"
                    />
                    <VImg
                      v-else-if="isZipItem(item)"
                      :src="zipPreviewImage"
                      class="w-100 mx-auto file-preview-image"
                    />
                    <div
                      v-else
                      class="d-flex flex-column align-center justify-center file-fallback-box rounded pa-4"
                    >
                      <VIcon size="36" icon="ri-file-3-line" />
                      <span class="text-caption mt-2">No preview</span>
                    </div>
                    <div class="mt-2 file-meta">
                      <span class="clamp-text text-wrap">
                        {{ item.name }}
                      </span>
                      <span class="file-size-text">
                        {{ formatFileSize(item.size ?? item.file?.size) }}
                      </span>
                    </div>
                  </VCardText>
                  <VCardActions class="file-card-actions w-100">
                    <VBtn
                      class="file-card-btn"
                      variant="elevated"
                      color="primary"
                      size="small"
                      @click.stop="downloadAt(index)"
                    >
                      Download
                    </VBtn>
                    <VBtn
                      class="file-card-btn"
                      variant="elevated"
                      color="error"
                      size="small"
                      @click.stop="removeAt(index)"
                    >
                      Remove
                    </VBtn>
                  </VCardActions>
                </VCard>
              </VCol>
            </template>
          </VRow>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.file-upload-zone {
  border: 1px dashed rgba(var(--v-theme-on-surface), var(--v-border-opacity));
}

.file-preview-image {
  aspect-ratio: 4 / 3;
  max-height: 150px;
  object-fit: contain;
}

.file-card {
  min-height: 320px;
  display: flex;
  flex-direction: column;
}

.file-card-col {
  flex: 0 0 clamp(190px, 28vw, 260px) !important;
  max-width: clamp(190px, 28vw, 260px) !important;
}

.file-card-content {
  flex: 1 1 auto;
}

.file-meta {
  display: flex;
  flex-direction: column;
}

.file-size-text {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.file-card-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: auto;
}

.file-card-btn {
  min-width: clamp(88px, 12vw, 120px);
  font-size: clamp(0.72rem, 1.4vw, 0.85rem);
  padding-inline: clamp(8px, 1.5vw, 14px);
}

.file-fallback-box {
  min-height: 150px;
  border: 1px solid rgba(var(--v-theme-on-surface), var(--v-border-opacity));
}

@media (max-width: 860px) {
  .file-card-actions {
    grid-template-columns: 1fr;
  }
}
</style>
