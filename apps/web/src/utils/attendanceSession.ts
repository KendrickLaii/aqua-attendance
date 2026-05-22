/** Cookie keys used by the attendance app (and mirrored template keys on login). */
export function isAttendanceLoggedIn(): boolean {
  return !!(
    useCookie('attendanceAccessToken').value
    && useCookie('attendanceUserData').value
  )
}

export function getAttendanceRole(): string | undefined {
  const raw = useCookie('attendanceUserData').value
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

/** Clear attendance + template auth cookies set on attendance login. */
export function clearAttendanceSessionCookies() {
  useCookie('attendanceAccessToken').value = null
  useCookie('attendanceRefreshToken').value = null
  useCookie('attendanceUserData').value = null
  useCookie('userData').value = null
  useCookie('accessToken').value = null
  useCookie('userAbilityRules').value = null
}
