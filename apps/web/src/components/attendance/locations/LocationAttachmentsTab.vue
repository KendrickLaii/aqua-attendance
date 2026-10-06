<script setup lang="ts">
import {
  type LocationAttachment,
  type LocationAttachmentList,
  deleteLocationAttachment,
  downloadLocationAttachment,
  listLocationAttachments,
  uploadLocationAttachment,
} from '@/api/attendance/locationAttachments'
import { useToast } from '@/composables/useToast'
import { formatApiError } from '@/utils/formatApiDetail'

const props = defineProps<{
  locationId: string | null
}>()

const { show: showToast } = useToast()

const data = ref<LocationAttachmentList | null>(null)
const loading = ref(false)
const uploading = ref(false)
const month = ref('')
const caption = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const deleteTarget = ref<LocationAttachment | null>(null)
const deleting = ref(false)

const perMonth = computed(() => data.value?.per_month ?? 2)

const usedByMonth = computed(() => {
  const counts: Record<string, number> = {}

  for (const item of data.value?.items ?? [])
    counts[item.month] = (counts[item.month] ?? 0) + 1

  return counts
})

const monthOptions = computed(() => {
  if (!data.value)
    return []

  const [year, mon] = data.value.current_month.split('-').map(Number)
  const [earliestYear, earliestMon] = data.value.earliest_month.split('-').map(Number)
  const total = (year * 12 + mon - 1) - (earliestYear * 12 + earliestMon - 1) + 1
  const options: { title: string; value: string }[] = []

  for (let i = 0; i < total; i++) {
    const index = year * 12 + (mon - 1) - i
    const value = `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`

    options.push({ title: `${value}  (${usedByMonth.value[value] ?? 0}/${perMonth.value})`, value })
  }

  return options
})

const monthFull = computed(() => (usedByMonth.value[month.value] ?? 0) >= perMonth.value)

const groups = computed(() => {
  const map = new Map<string, LocationAttachment[]>()

  for (const item of data.value?.items ?? [])
    map.set(item.month, [...(map.get(item.month) ?? []), item])

  return [...map.entries()]
})

async function load() {
  if (!props.locationId) {
    data.value = null

    return
  }
  loading.value = true
  try {
    data.value = await listLocationAttachments(props.locationId)
    if (!month.value || !monthOptions.value.some(o => o.value === month.value))
      month.value = data.value.current_month
  }
  catch (error) {
    showToast(formatApiError(error, 'Failed to load attachments'), 'error')
  }
  finally {
    loading.value = false
  }
}

watch(() => props.locationId, load, { immediate: true })

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
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
    await uploadLocationAttachment(props.locationId, file, month.value, caption.value)
    caption.value = ''
    showToast('Attachment uploaded')
    await load()
  }
  catch (error) {
    showToast(formatApiError(error, 'Upload failed'), 'error')
  }
  finally {
    uploading.value = false
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
      type="info"
      variant="tonal"
      density="compact"
      class="mb-4"
    >
      Superadmin only. Up to {{ perMonth }} images per month; files older than 24 months are deleted automatically.
    </VAlert>

    <VAlert
      v-if="!locationId"
      type="warning"
      variant="tonal"
      density="compact"
    >
      Save the location first, then reopen it to add attachments.
    </VAlert>

    <template v-else>
      <input
        ref="fileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        class="d-none"
        @change="onFileChange"
      >

      <VRow dense>
        <VCol
          cols="12"
          sm="4"
        >
          <VSelect
            v-model="month"
            :items="monthOptions"
            label="Month"
            density="compact"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="5"
        >
          <VTextField
            v-model="caption"
            label="Caption (optional)"
            density="compact"
            maxlength="255"
            hide-details
          />
        </VCol>
        <VCol
          cols="12"
          sm="3"
        >
          <VBtn
            block
            variant="tonal"
            prepend-icon="ri-upload-2-line"
            :loading="uploading"
            :disabled="monthFull || !month"
            @click="fileInput?.click()"
          >
            Upload
          </VBtn>
        </VCol>
      </VRow>
      <div
        v-if="monthFull"
        class="text-caption text-warning mt-1"
      >
        {{ month }} is full ({{ perMonth }}/{{ perMonth }}). Delete one or pick another month.
      </div>

      <VProgressLinear
        v-if="loading"
        indeterminate
        class="mt-4"
      />
      <div
        v-else-if="!groups.length"
        class="text-body-2 text-medium-emphasis mt-4"
      >
        No attachments yet.
      </div>

      <div
        v-for="[groupMonth, items] in groups"
        :key="groupMonth"
        class="mt-4"
      >
        <div class="text-subtitle-2 mb-1">
          {{ groupMonth }}
          <span class="text-caption text-medium-emphasis">({{ items.length }}/{{ perMonth }})</span>
        </div>
        <VCard
          v-for="item in items"
          :key="item.id"
          variant="outlined"
          class="pa-2 mb-2 d-flex align-center"
        >
          <VIcon
            icon="ri-image-line"
            class="me-2"
          />
          <div class="flex-grow-1 text-truncate">
            <div class="text-body-2 text-truncate">
              {{ item.original_name }}
            </div>
            <div class="text-caption text-medium-emphasis text-truncate">
              {{ formatSize(item.size) }}{{ item.caption ? ` · ${item.caption}` : '' }}
            </div>
          </div>
          <VBtn
            icon="ri-download-2-line"
            size="small"
            variant="text"
            title="Download"
            @click="onDownload(item)"
          />
          <VBtn
            icon="ri-delete-bin-line"
            size="small"
            variant="text"
            color="error"
            title="Delete"
            @click="deleteTarget = item"
          />
        </VCard>
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
