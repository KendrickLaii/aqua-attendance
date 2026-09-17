import { $attendanceApi } from '@/utils/attendanceApi'

export interface UploadResult {
  url: string
  key: string
  content_type: string
  size: number
}

export async function uploadMedia(file: File): Promise<UploadResult> {
  const body = new FormData()

  body.append('file', file)

  return await $attendanceApi<UploadResult>('/uploads', {
    method: 'POST',
    body,
  })
}
