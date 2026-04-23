import { ofetch } from 'ofetch'

export const $attendanceApi = ofetch.create({
  baseURL: import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api',
  async onRequest({ options }) {
    const accessToken = useCookie('attendanceAccessToken').value
    if (accessToken) {
      if (!options.headers)
        options.headers = new Headers()
      if (options.headers instanceof Headers)
        options.headers.set('Authorization', `Bearer ${accessToken}`)
    }
  },
  async onResponseError({ response }) {
    if (response.status === 401) {
      const refreshToken = useCookie('attendanceRefreshToken').value
      if (refreshToken) {
        try {
          const data = await ofetch(`${import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api'}/auth/refresh`, {
            method: 'POST',
            body: { refresh_token: refreshToken },
          })
          useCookie('attendanceAccessToken').value = data.access_token
          useCookie('attendanceRefreshToken').value = data.refresh_token
        }
        catch {
          useCookie('attendanceAccessToken').value = null
          useCookie('attendanceRefreshToken').value = null
          useCookie('attendanceUserData').value = null
        }
      }
    }
  },
})
