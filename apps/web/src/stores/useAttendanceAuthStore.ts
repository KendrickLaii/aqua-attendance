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
      useCookie('accessToken').value = tokens.access_token
      useCookie('refreshToken').value = tokens.refresh_token
      const me = await attendanceGetMe()
      this.user = me
      this.isLoggedIn = true
      // Template-compatible shape so navbar + CASL work without mirroring
      useCookie('userData').value = JSON.stringify({
        id: me.id,
        username: me.username,
        role: me.role,
        fullName: me.full_name,
      })
    },
    async logout() {
      const refreshToken = useCookie('refreshToken').value
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
      const raw = useCookie('userData').value
      const token = useCookie('accessToken').value
      if (raw && token) {
        try {
          const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
          // Normalise template shape (fullName) back to API shape (full_name)
          this.user = {
            ...parsed,
            full_name: parsed.fullName ?? parsed.full_name ?? '',
            email: parsed.email ?? '',
            is_active: parsed.is_active ?? true,
            created_at: parsed.created_at ?? '',
            updated_at: parsed.updated_at ?? '',
          } as AttendanceUser
          this.isLoggedIn = true
        }
        catch {
          this.logout()
        }
      }
    },
  },
})
