import { getAllowedRouteNames } from '@/navigation/vertical'
import { canNavigate } from '@layouts/plugins/casl'
import { getAttendanceRole, isAttendanceLoggedIn } from '@/utils/attendanceSession'
import type { RouteNamedMap, _RouterTyped } from 'unplugin-vue-router'

const ATTENDANCE_PUBLIC_ROUTE_NAMES = new Set(['attendance-login', 'attendance'])

function resolveAttendanceRedirectTarget(to: { query: Record<string, unknown>; fullPath: string }) {
  const raw = to.query.to
  const target = typeof raw === 'string'
    ? raw.trim()
    : Array.isArray(raw)
      ? String(raw[0] ?? '').trim()
      : ''

  if (
    target.startsWith('/attendance')
    && target !== '/attendance'
    && !target.startsWith('/attendance/login')
  )
    return target

  return { name: 'attendance-dashboard' as const }
}

export const setupGuards = (router: _RouterTyped<RouteNamedMap & { [key: string]: any }>) => {
  const allowedRouteNames = getAllowedRouteNames()

  router.beforeEach(to => {
    if (to.meta.public)
      return

    if (to.path.startsWith('/attendance')) {
      const routeName = typeof to.name === 'string' ? to.name : ''
      const isPublicAttendance = ATTENDANCE_PUBLIC_ROUTE_NAMES.has(routeName)
      const loggedIn = isAttendanceLoggedIn()

      if (!isPublicAttendance && !loggedIn) {
        return {
          name: 'attendance-login',
          query: to.fullPath !== '/attendance' && !to.fullPath.endsWith('/login')
            ? { to: to.fullPath }
            : undefined,
        }
      }

      if (routeName === 'attendance-login' && loggedIn)
        return resolveAttendanceRedirectTarget(to)

      if (loggedIn && to.path.startsWith('/attendance/users')) {
        const role = getAttendanceRole()
        if (role !== 'admin' && role !== 'superadmin')
          return { name: 'not-authorized' }
      }

      return
    }

    const userDataCookie = useCookie('userData')
    const accessTokenCookie = useCookie('accessToken')
    const isLoggedIn = !!(userDataCookie.value && accessTokenCookie.value)

    const role = (userDataCookie.value as any)?.role
    if (isLoggedIn && to.path.startsWith('/attendance/users') && role !== 'admin' && role !== 'superadmin')
      return { name: 'not-authorized' }

    if (to.meta.unauthenticatedOnly) {
      if (isLoggedIn)
        return '/'
      else
        return undefined
    }

    const bypassNavCheck = new Set(['index', 'login', 'attendance-login', 'attendance', 'not-authorized', '$error'])
    if (
      isLoggedIn
      && to.name
      && typeof to.name === 'string'
      && !bypassNavCheck.has(to.name)
      && !allowedRouteNames.has(to.name)
    )
      return { name: '$error', params: { error: 'not-found' } }

    if (!canNavigate(to) && to.matched.length) {
      return isLoggedIn
        ? { name: 'not-authorized' }
        : {
            name: 'attendance-login',
            query: {
              ...to.query,
              to: to.fullPath !== '/' ? to.path : undefined,
            },
          }
    }
  })
}
