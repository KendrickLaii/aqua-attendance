import { $attendanceApi } from '@/utils/attendanceApi'

export interface LocationAttachment {
  id: string
  location_id: string
  month: string
  original_name: string
  content_type: string
  size: number
  caption: string | null
  created_at: string
}

export interface LocationAttachmentList {
  earliest_month: string
  current_month: string
  per_month: number
  items: LocationAttachment[]
}

const base = (locationId: string) => `/locations/${locationId}/attachments`

export function listLocationAttachments(locationId: string) {
  return $attendanceApi<LocationAttachmentList>(base(locationId))
}

export function uploadLocationAttachment(locationId: string, file: File, month: string, caption?: string) {
  const body = new FormData()

  body.append('file', file)
  body.append('month', month)
  if (caption?.trim())
    body.append('caption', caption.trim())

  return $attendanceApi<LocationAttachment>(base(locationId), { method: 'POST', body })
}

export function deleteLocationAttachment(locationId: string, attachmentId: string) {
  return $attendanceApi<void>(`${base(locationId)}/${attachmentId}`, { method: 'DELETE' })
}

export async function downloadLocationAttachment(locationId: string, attachment: LocationAttachment) {
  const blob = await $attendanceApi<Blob>(`${base(locationId)}/${attachment.id}/download`, { responseType: 'blob' })
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = objectUrl
  link.download = attachment.original_name
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
