import { ref, watch, onMounted } from 'vue'
import type { Ref } from 'vue'
import { getAttachmentByWorkingUuid, oneDriveGet } from '@/api/attachment'
import type { TaxAttachmentListItem, TaxAttachmentRecord } from '@/types/attachment'
import { useToast } from '@/composables/useToast'

/**
 * useAttachments composable
 *
 * WHY this exists:
 *   Review.vue had ~100 lines of attachment-related state & logic mixed in with
 *   tax computation and formatting code. By extracting it into a composable we:
 *     1. Keep attachment concerns isolated and testable.
 *     2. Let the composable own its own reactive state (attachmentData, attachmentList).
 *     3. Expose only the methods the parent actually needs (payload builder, uuid getter, oneDrive opener).
 *
 * WHAT it does:
 *   - Loads attachment records from the API when `workingRecordUuid` changes.
 *   - Normalises the raw API response into a uniform `TaxAttachmentListItem[]`.
 *   - Converts local File objects to base64 data URLs for the save payload.
 *   - Opens the company's Tax folder in OneDrive.
 */

// ────────────────────────────────────────────
// Attachment payload item types
// ────────────────────────────────────────────

/** Shape of a NEW file (uploaded locally) when sent in the save payload. */
interface AttachmentPayloadFileItem {
  name: string
  type: string
  size: number
  data: string // base64 data URL
}

/** Shape of an EXISTING file (already on server) when sent in the save payload. */
interface AttachmentPayloadUrlItem {
  name: string
  url: string
  size?: number
}

export type AttachmentPayloadItem = AttachmentPayloadFileItem | AttachmentPayloadUrlItem

// ────────────────────────────────────────────
// Internal helpers
// ────────────────────────────────────────────

/**
 * Normalise the raw `attachment_list` from the API into a clean array.
 *
 * The API can return items in several shapes:
 *   - Plain URL strings
 *   - Objects with { url, name, size }
 *   - Objects with { data, filename }
 * This function handles all of them so the rest of the code only sees `TaxAttachmentListItem[]`.
 */
function normalizeAttachmentListFromApi(raw: unknown): TaxAttachmentListItem[] {
  if (!Array.isArray(raw))
    return []

  const out: TaxAttachmentListItem[] = []
  for (const item of raw) {
    if (typeof item === 'string') {
      const url = item.trim()
      if (url)
        out.push({ name: url.split('/').pop() || 'attachment', url })
      continue
    }
    if (!item || typeof item !== 'object')
      continue
    const o = item as Record<string, unknown>
    const url = String(o.url ?? o.data ?? '').trim()
    const name = (String(o.name ?? o.filename ?? 'attachment').trim() || 'attachment')
    const size = typeof o.size === 'number' ? o.size : undefined
    if (url)
      out.push({ name, url, size })
  }
  return out
}

/** Convert a File to a base64 data URL string (used before uploading). */
function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsDataURL(file)
  })
}

// ────────────────────────────────────────────
// Composable
// ────────────────────────────────────────────

interface UseAttachmentsOptions {
  /** Reactive ref (or getter) that provides the current working record UUID. */
  workingRecordUuid: Ref<string | undefined>
  /** Basic info needed for OneDrive folder lookup. */
  companyNameEn: Ref<string>
  fiscalYearEnd: Ref<string>
}

export function useAttachments(options: UseAttachmentsOptions) {
  const { show: showToast } = useToast()

  // ── Reactive state ──
  const attachmentData = ref<TaxAttachmentRecord | null>(null)
  const attachmentList = ref<TaxAttachmentListItem[]>([])
  const isOneDriveButtonLoading = ref(false)

  // ── Load from API ──
  async function loadAttachments() {
    const uuid = options.workingRecordUuid.value
    if (!uuid) {
      attachmentData.value = null
      attachmentList.value = []
      return
    }

    try {
      const res = await getAttachmentByWorkingUuid(uuid)
      if (res?.status_code === 200) {
        attachmentData.value = res?.data ?? null
        attachmentList.value = normalizeAttachmentListFromApi(attachmentData.value?.attachment_list)
      }
    }
    catch (error) {
      console.error('Failed to fetch attachment:', error)
      attachmentData.value = null
      attachmentList.value = []
      // Show user-facing feedback instead of silently swallowing the error
      showToast('Failed to load attachments', 'error')
    }
  }

  // ── Build payload for save ──
  /**
   * Converts the current attachmentList into a payload array ready for the API.
   * - Local File objects are base64-encoded via FileReader.
   * - Existing server URLs are passed through as-is.
   */
  async function getAttachmentListForPayload(): Promise<AttachmentPayloadItem[]> {
    const out: AttachmentPayloadItem[] = []
    for (const item of attachmentList.value) {
      if (item.file) {
        const data = await fileToDataUrl(item.file)
        out.push({
          name: item.name,
          type: item.file.type,
          size: item.file.size,
          data,
        })
      }
      else {
        out.push({
          name: item.name,
          url: item.url,
          size: item.size,
        })
      }
    }
    return out
  }

  /** Returns the UUID of the current attachment record (empty string if none). */
  function getAttachmentRecordUuid(): string {
    return attachmentData.value?.uuid ?? ''
  }

  // ── OneDrive integration ──
  async function openOneDrive() {
    isOneDriveButtonLoading.value = true
    // Extract year from fiscal year end date (format: "DD-MM-YYYY" or "YYYY-MM-DD")
    const year = options.fiscalYearEnd.value?.split('-').pop() ?? ''
    try {
      const res = await oneDriveGet({
        company_name: options.companyNameEn.value ?? '',
        year,
        folder_name: 'Tax',
      })
      if ((res as Record<string, unknown>)?.status_code === 200) {
        window.open((res as Record<string, unknown> & { data: { folderUrl: string } }).data.folderUrl, '_blank')
      }
    }
    catch (e) {
      console.error(e)
      showToast('Open OneDrive failed, please try again', 'error')
    }
    finally {
      isOneDriveButtonLoading.value = false
    }
  }

  // ── Auto-load when workingRecordUuid changes ──
  watch(options.workingRecordUuid, async (value, oldValue) => {
    if (!value || value === oldValue) return
    await loadAttachments()
  })

  onMounted(async () => {
    await loadAttachments()
  })

  return {
    // State (template binds to these)
    attachmentData,
    attachmentList,
    isOneDriveButtonLoading,

    // Methods (called by parent or exposed via defineExpose)
    getAttachmentListForPayload,
    getAttachmentRecordUuid,
    openOneDrive,
  }
}
