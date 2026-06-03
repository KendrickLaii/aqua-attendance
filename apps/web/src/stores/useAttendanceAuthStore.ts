import { defineStore } from 'pinia'
import { attendanceGetMe, attendanceLogin, attendanceLogout } from '@/api/attendance/auth'
import type { AttendanceUser, AttendanceLoginPayload } from '@/api/attendance/auth'
import { clearAttendanceSessionCookies } from '@/utils/attendanceSession'

export const useAttendanceAuthStore = defineStore('attendanceAuth', {
  state: () => ({
    user: null as AttendanceUser | null,
    isLoggedIn: false,
  }),
  getters: {
    role: (state) => state.user?.role ?? null,
    isAdmin: (state) => state.user?.role === 'admin' || state.user?.role === 'superadmin',
    isSuperAdmin: (state) => state.user?.role === 'superadmin',
  },
  actions: {
    async login(payload: AttendanceLoginPayload) {
      const tokens = await attendanceLogin(payload)
      useCookie('attendanceAccessToken').value = tokens.access_token
      useCookie('attendanceRefreshToken').value = tokens.refresh_token
      const me = await attendanceGetMe()
      this.user = me
      this.isLoggedIn = true
      useCookie('attendanceUserData').value = JSON.stringify(me)
    },
    async logout() {
      const refreshToken = useCookie('attendanceRefreshToken').value
      if (refreshToken) {
        try {
          await attendanceLogout(refreshToken)
        }
        catch {
          // still clear local session if API is down or token already invalid
        }
      }
      clearAttendanceSessionCookies()
      this.user = null
      this.isLoggedIn = false
    },
    restoreSession() {
      const raw = useCookie('attendanceUserData').value
      const token = useCookie('attendanceAccessToken').value
      if (raw && token) {
        try {
          this.user = typeof raw === 'string' ? JSON.parse(raw) : raw
          this.isLoggedIn = true
        }
        catch {
          this.logout()
        }
      }
    },
  },
})
