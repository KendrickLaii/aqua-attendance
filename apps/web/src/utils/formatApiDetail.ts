export function formatApiDetail(detail: unknown): string {
  if (detail == null)
    return ''
  if (typeof detail === 'string')
    return detail
  if (Array.isArray(detail)) {
    return detail
      .filter((e): e is Record<string, unknown> => Boolean(e && typeof e === 'object'))
      .map(e => {
        const loc = e.loc
        const msg = e.msg
        const path = Array.isArray(loc) ? loc.filter((x): x is string => typeof x === 'string' && x !== 'body').join('.') : ''

        return path ? `${path}: ${msg}` : String(msg ?? 'Invalid value')
      })
      .join(' · ')
  }

  return String(detail)
}

export function formatApiError(e: unknown, fallback: string): string {
  const data = e && typeof e === 'object' && 'data' in e
    ? (e as { data?: { detail?: unknown; error?: string }; statusCode?: number }).data
    : undefined

  const status = e && typeof e === 'object' && 'statusCode' in e ? (e as { statusCode?: number }).statusCode : undefined
  const rawMessage = formatApiDetail(data?.detail)
    || data?.error
    || (e instanceof Error ? e.message : fallback)

  if (status === 429) {
    return `${rawMessage || 'Too many requests'}. Please try again later.`
  }

  return rawMessage
}
