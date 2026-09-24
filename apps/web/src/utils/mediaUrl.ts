/** Turn a stored location photo URL into an <img src> the browser can load. */
export function resolveMediaUrl(url: string | null | undefined): string {
  const trimmed = (url ?? '').trim()
  if (!trimmed)
    return ''
  if (/^(https?:|blob:|data:)/i.test(trimmed))
    return trimmed

  const apiBase = String(import.meta.env?.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api').replace(/\/$/, '')
  const path = trimmed.startsWith('/') ? trimmed : `/${trimmed}`

  // Production can bake VITE_ATTENDANCE_API_URL=/api (same origin via Caddy).
  if (apiBase.startsWith('/'))
    return path

  const origin = apiBase.replace(/\/api$/i, '')

  return `${origin}${path}`
}

/** Uploads are public UUID URLs, so <img> and print load them directly. */
export function needsAuthenticatedMediaFetch(_url: string | null | undefined): boolean {
  return false
}
