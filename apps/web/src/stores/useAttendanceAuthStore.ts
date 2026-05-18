import { defineStore } from 'pinia'
import { attendanceGetMe, attendanceLogin } from '@/api/attendance/auth'
import type { AttendanceUser, AttendanceLoginPayload } from '@/api/attendance/auth'

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
    logout() {
      useCookie('attendanceAccessToken').value = null
      useCookie('attendanceRefreshToken').value = null
      useCookie('attendanceUserData').value = null
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
