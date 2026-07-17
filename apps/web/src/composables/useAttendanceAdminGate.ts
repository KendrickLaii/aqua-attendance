import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'

/**
 * Shared attendance session gate for admin pages.
 * Returns false after redirecting when the session is missing or not admin.
 */
export function useAttendanceAdminGate() {
  const authStore = useAttendanceAuthStore()
  const router = useRouter()

  async function ensureAccess(options?: { requireAdmin?: boolean }): Promise<boolean> {
    const requireAdmin = options?.requireAdmin ?? true

    authStore.restoreSession()
    if (!authStore.isLoggedIn) {
      await router.replace({ name: 'attendance-login' })

      return false
    }
    if (requireAdmin && !authStore.isAdmin) {
      await router.replace({ name: 'attendance-dashboard' })

      return false
    }

    return true
  }

  return { authStore, ensureAccess }
}
