import { useAbility } from '@casl/vue'
import { attendanceRoleToCaslRules } from '@/utils/attendanceCasl'

/**
 * Keeps @casl/vue in sync with the attendance session. The CASL plugin only reads
 * `userAbilityRules` once at startup; without this, SPA login never updates the ability
 * and admin-only nav items (e.g. User Management) stay hidden.
 */
export function useAttendanceCaslSync() {
  const ability = useAbility()
  const route = useRoute()

  const syncFromAttendanceSession = () => {
    if (!route.path.startsWith('/attendance'))
      return

    if (route.name === 'attendance-login')
      return

    const token = useCookie('accessToken').value
    const raw = useCookie('userData').value
    if (!token || !raw)
      return

    let role: string | undefined
    try {
      const user = typeof raw === 'string' ? JSON.parse(raw) as { role?: string } : (raw as { role?: string })
      role = user?.role
    }
    catch {
      return
    }

    const rules = attendanceRoleToCaslRules(role)

    ability.update(rules)
    useCookie('userAbilityRules').value = rules as any
  }

  watch(() => route.fullPath, syncFromAttendanceSession, { immediate: true })
}
