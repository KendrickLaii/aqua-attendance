/** Canonical cookie names shared between attendance app and AQUA template. */

export const SCAN_TOKEN_SESSION_KEY = 'attendance-scan-token'
export const SCAN_ENTRY_SESSION_KEY = 'attendance-scan-entry'

export function isAttendanceLoggedIn(): boolean {
  return !!(
    useCookie('accessToken').value
    && useCookie('userData').value
  )
}

export function getAttendanceRole(): string | undefined {
  const raw = useCookie('userData').value
  if (!raw)
    return undefined
  try {
    const user = typeof raw === 'string' ? JSON.parse(raw) : raw
    return user?.role as string | undefined
  }
  catch {
    return undefined
  }
}

/** Clear all auth cookies (used by attendance login and template logout). */
export function clearAttendanceSessionCookies() {
  useCookie('accessToken').value = null
  useCookie('refreshToken').value = null
  useCookie('userData').value = null
  useCookie('userAbilityRules').value = null
}
