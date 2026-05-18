import { getAllowedRouteNames } from '@/navigation/vertical'
import { canNavigate } from '@layouts/plugins/casl'
import type { RouteNamedMap, _RouterTyped } from 'unplugin-vue-router'

export const setupGuards = (router: _RouterTyped<RouteNamedMap & { [key: string]: any }>) => {
  const allowedRouteNames = getAllowedRouteNames()

  router.beforeEach(to => {
    if (to.meta.public)
      return

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

    const bypassNavCheck = new Set(['index', 'login', 'attendance-login', 'attendance', 'attendance-scanner', 'not-authorized', '$error'])
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
