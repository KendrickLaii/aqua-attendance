<script setup lang="ts">
import {
  type LocationAttachment,
  type LocationAttachmentList,
  deleteLocationAttachment,
  downloadLocationAttachment,
  fetchLocationAttachmentBlob,
  listLocationAttachments,
  uploadLocationAttachment,
} from '@/api/attendance/locationAttachments'
import { useToast } from '@/composables/useToast'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  locationId: string | null
}>()

const RETENTION_MONTHS = 24

const { show: showToast } = useToast()

const data = ref<LocationAttachmentList | null>(null)
const loading = ref(false)
const loadError = ref('')
const uploading = ref(false)
const uploadingSlot = ref(-1)
const month = ref('')
const captions = reactive<Record<number, string>>({})
const fileInput = ref<HTMLInputElement | null>(null)
const deleteTarget = ref<LocationAttachment | null>(null)
const deleting = ref(false)
const thumbs = reactive<Record<string, string>>({})

const perMonth = computed(() => data.value?.per_month ?? 2)

function monthKey(index: number) {
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`
}

const currentMonth = computed(() => {
  if (data.value)
    return data.value.current_month

  const now = new Date()

  return monthKey(now.getFullYear() * 12 + now.getMonth())
})

const monthList = computed(() => {
  const [year, mon] = currentMonth.value.split('-').map(Number)

  return Array.from({ length: RETENTION_MONTHS }, (_, i) => monthKey(year * 12 + (mon - 1) - i))
})

const usedByMonth = computed(() => {
  const counts: Record<string, number> = {}

  for (const item of data.value?.items ?? [])
    counts[item.month] = (counts[item.month] ?? 0) + 1

  return counts
})

const monthOptions = computed(() =>
  monthList.value.map(value => ({
    title: `${value}  ·  ${usedByMonth.value[value] ?? 0}/${perMonth.value}`,
    value,
  })),
)

const monthsWithFiles = computed(() => monthList.value.filter(m => usedByMonth.value[m]))

const slots = computed(() => {
  const items = (data.value?.items ?? []).filter(i => i.month === month.value)

  return Array.from({ length: perMonth.value }, (_, i) => items[i] ?? null)
})

async function loadThumb(item: LocationAttachment) {
  if (!props.locationId || thumbs[item.id])
    return
  try {
    thumbs[item.id] = URL.createObjectURL(await fetchLocationAttachmentBlob(props.locationId, item.id))
  }
  catch {
    // thumbnail is optional
  }
}

function dropThumb(id: string) {
  if (thumbs[id]) {
    URL.revokeObjectURL(thumbs[id])
    delete thumbs[id]
  }
}

async function load() {
  if (!props.locationId) {
    data.value = null

    return
  }
  loading.value = true
  loadError.value = ''
  try {
    data.value = await listLocationAttachments(props.locationId)
    if (!month.value)
      month.value = data.value.current_month
  }
  catch (error) {
    loadError.value = formatApiError(error, 'Failed to load attachments')
  }
  finally {
    loading.value = false
  }
}

watch(() => props.locationId, load, { immediate: true })
watch(month, () => Object.keys(captions).forEach(k => delete captions[Number(k)]))
watch(currentMonth, value => {
  if (!month.value)
    month.value = value
}, { immediate: true })

watch([() => data.value, month], () => {
  for (const item of slots.value) {
    if (item)
      loadThumb(item)
  }
}, { immediate: true })

onBeforeUnmount(() => Object.keys(thumbs).forEach(dropThumb))

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function pickFile(slotIndex: number) {
  uploadingSlot.value = slotIndex
  fileInput.value?.click()
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  input.value = ''
  if (!file || !props.locationId)
    return
  if (!file.type.startsWith('image/')) {
    showToast('Please choose a JPEG, PNG, WebP, or GIF image', 'error')

    return
  }
  uploading.value = true
  try {
    await uploadLocationAttachment(props.locationId, file, month.value, captions[uploadingSlot.value])
    delete captions[uploadingSlot.value]
    showToast('Attachment uploaded')
    await load()
  }
  catch (error) {
    showToast(formatApiError(error, 'Upload failed'), 'error')
  }
  finally {
    uploading.value = false
    uploadingSlot.value = -1
  }
}

async function onDownload(item: LocationAttachment) {
  if (!props.locationId)
    return
  try {
    await downloadLocationAttachment(props.locationId, item)
  }
  catch (error) {
    showToast(formatApiError(error, 'Download failed'), 'error')
  }
}

async function confirmDelete() {
  if (!props.locationId || !deleteTarget.value)
    return
  deleting.value = true
  try {
    await deleteLocationAttachment(props.locationId, deleteTarget.value.id)
    dropThumb(deleteTarget.value.id)
    deleteTarget.value = null
    showToast('Attachment deleted')
    await load()
  }
  catch (error) {
    showToast(formatApiError(error, 'Delete failed'), 'error')
  }
  finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="mt-1">
    <VAlert
      v-if="!locationId"
      type="warning"
      variant="tonal"
      density="compact"
    >
      Save this location first, then reopen it to add attachments.
    </VAlert>

    <template v-else>
      <input
        ref="fileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        class="d-none"
        @change="onFileChange"
      >

      <VAlert
        v-if="loadError"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        {{ loadError }}
        <template #append>
          <VBtn
            size="small"
            variant="text"
            @click="load"
          >
            Retry
          </VBtn>
        </template>
      </VAlert>

      <VRow dense>
        <VCol
          cols="12"
          sm="6"
        >
          <VSelect
            v-model="month"
            :items="monthOptions"
            label="Month"
            density="compact"
            prepend-inner-icon="ri-calendar-line"
            hide-details
          />
        </VCol>
      </VRow>

      <VProgressLinear
        v-if="loading"
        indeterminate
        class="mt-4"
      />

      <VRow class="mt-1">
        <VCol
          v-for="(item, index) in slots"
          :key="item?.id ?? `empty-${index}`"
          cols="12"
          sm="6"
        >
          <VCard
            variant="outlined"
            class="attachment-slot"
          >
            <template v-if="item">
              <VImg
                :src="thumbs[item.id]"
                height="140"
                cover
                class="bg-grey-lighten-4"
              >
                <template #placeholder>
                  <div class="d-flex align-center justify-center fill-height">
                    <VIcon icon="ri-image-line" />
                  </div>
                </template>
              </VImg>
              <div class="pa-3">
                <div class="text-body-2 text-truncate">
                  {{ item.original_name }}
                </div>
                <div class="text-caption text-medium-emphasis text-truncate">
                  {{ formatSize(item.size) }}{{ item.caption ? ` · ${item.caption}` : '' }}
                </div>
                <div class="d-flex mt-2 gap-1">
                  <VBtn
                    size="small"
                    variant="tonal"
                    prepend-icon="ri-download-2-line"
                    @click="onDownload(item)"
                  >
                    Download
                  </VBtn>
                  <VBtn
                    size="small"
                    variant="text"
                    color="error"
                    prepend-icon="ri-delete-bin-line"
                    @click="deleteTarget = item"
                  >
                    Delete
                  </VBtn>
                </div>
              </div>
            </template>

            <div
              v-else
              class="attachment-slot__empty"
            >
              <VTextField
                v-model="captions[index]"
                label="Note (optional)"
                density="compact"
                maxlength="255"
                hide-details
                :disabled="uploading"
              />
              <VBtn
                block
                variant="tonal"
                class="mt-3"
                prepend-icon="ri-upload-2-line"
                :loading="uploading && uploadingSlot === index"
                :disabled="uploading || !month"
                @click="pickFile(index)"
              >
                Choose image
              </VBtn>
              <div class="text-caption text-medium-emphasis text-center mt-2">
                Slot {{ index + 1 }} of {{ perMonth }} · {{ month }}
              </div>
            </div>
          </VCard>
        </VCol>
      </VRow>

      <div
        v-if="monthsWithFiles.length"
        class="mt-4"
      >
        <div class="text-caption text-medium-emphasis mb-1">
          Months with files
        </div>
        <div class="d-flex flex-wrap gap-2">
          <VChip
            v-for="m in monthsWithFiles"
            :key="m"
            size="small"
            :color="m === month ? 'primary' : undefined"
            :variant="m === month ? 'flat' : 'tonal'"
            @click="month = m"
          >
            {{ m }} · {{ usedByMonth[m] }}/{{ perMonth }}
          </VChip>
        </div>
      </div>

      <div class="text-caption text-medium-emphasis mt-4">
        Visible to superadmin only. Files older than {{ RETENTION_MONTHS }} months are removed automatically.
      </div>
    </template>

    <VDialog
      :model-value="!!deleteTarget"
      max-width="380"
      @update:model-value="deleteTarget = null"
    >
      <VCard title="Delete attachment?">
        <VCardText>{{ deleteTarget?.original_name }} will be permanently removed.</VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn @click="deleteTarget = null">
            Cancel
          </VBtn>
          <VBtn
            color="error"
            :loading="deleting"
            @click="confirmDelete"
          >
            Delete
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.attachment-slot {
  overflow: hidden;
  min-height: 140px;
}

.attachment-slot__empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 200px;
  padding: 16px;
}
</style>
