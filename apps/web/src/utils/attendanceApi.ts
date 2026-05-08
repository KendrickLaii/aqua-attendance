import { FetchError, ofetch } from 'ofetch'

const getBaseURL = (): string =>
  import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api'

/**
 * Normalize headers then set Authorization from the latest cookie every time —
 * reused options objects can otherwise keep a stale Bearer after refresh.
 */
function attachAttendanceAuthHeaders(options: { headers?: HeadersInit }) {
  const headers = new Headers(options.headers ?? undefined)

  headers.delete('Authorization')
  headers.delete('authorization')

  const accessToken = useCookie('attendanceAccessToken').value
  if (accessToken)
    headers.set('Authorization', `Bearer ${accessToken}`)

  options.headers = headers
}

function isAttendanceAuthRequestUrl(request: Parameters<typeof ofetch>[0]): boolean {
  const s =
    typeof request === 'string'
      ? request
      : request instanceof Request
        ? request.url
        : typeof request?.toString === 'function'
          ? String(request)
          : ''

  return s.includes('/auth/login') || s.includes('/auth/register') || s.includes('/auth/refresh')
}

async function refreshAttendanceTokens(): Promise<boolean> {
  const refreshToken = useCookie('attendanceRefreshToken').value
  if (!refreshToken)
    return false

  try {
    const data = await ofetch<{ access_token: string; refresh_token: string }>(
      `${getBaseURL()}/auth/refresh`,
      {
        method: 'POST',
        body: { refresh_token: refreshToken },
      },
    )

    useCookie('attendanceAccessToken').value = data.access_token
    useCookie('attendanceRefreshToken').value = data.refresh_token

    return true
  }
  catch {
    useCookie('attendanceAccessToken').value = null
    useCookie('attendanceRefreshToken').value = null
    useCookie('attendanceUserData').value = null

    return false
  }
}

/** Single-flight inner client (401 handling is in $attendanceApi wrapper). */
const attendanceOfetch = ofetch.create({
  baseURL: getBaseURL(),
  async onRequest({ options }) {
    attachAttendanceAuthHeaders(options)
  },
})

export async function $attendanceApi<T = unknown>(
  request: Parameters<typeof attendanceOfetch>[0],
  options?: Exclude<Parameters<typeof attendanceOfetch>[1], undefined>,
): Promise<T> {
  const invoke = (): Promise<T> => attendanceOfetch<T>(request, options)

  try {
    return await invoke()
  }
  catch (error) {
    if (!(error instanceof FetchError))
      throw error

    const unauthorizedStatus =
      typeof error.status === 'number'
        ? error.status
        : 'statusCode' in error && typeof (error as { statusCode?: number }).statusCode === 'number'
          ? (error as { statusCode: number }).statusCode
          : undefined

    if (unauthorizedStatus !== 401)
      throw error

    if (!isAttendanceAuthRequestUrl(request))
    {
      const refreshed = await refreshAttendanceTokens()
      if (!refreshed)
        throw error

      try {
        return await invoke()
      }
      catch (retryError) {
        throw retryError
      }
    }

    throw error
  }
}
