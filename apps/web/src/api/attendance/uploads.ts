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

export function attendanceUploadRequestPath(url: string): string | null {
  const trimmed = url.trim()
  if (!trimmed)
    return null
  try {
    const parsed = new URL(trimmed, 'http://localhost')
    const match = parsed.pathname.match(/\/(?:api\/)?uploads\/(.+)$/)
    return match ? `/uploads/${match[1]}` : null
  }
  catch {
    const match = trimmed.match(/\/(?:api\/)?uploads\/(.+)$/)
    return match ? `/uploads/${match[1]}` : null
  }
}

export async function fetchUploadObjectUrl(url: string): Promise<string> {
  const path = attendanceUploadRequestPath(url)
  if (!path)
    throw new Error('Not an attendance upload URL')
  const blob = await $attendanceApi<Blob>(path, { responseType: 'blob' })

  return URL.createObjectURL(blob)
}

export async function resolvePrintLogoUrl(url: string | null | undefined): Promise<string> {
  const { needsAuthenticatedMediaFetch, resolveMediaUrl } = await import('@/utils/mediaUrl')
  const resolved = resolveMediaUrl(url)
  if (!needsAuthenticatedMediaFetch(resolved))
    return resolved
  try {
    return await fetchUploadObjectUrl(resolved)
  }
  catch {
    return resolved
  }
}
