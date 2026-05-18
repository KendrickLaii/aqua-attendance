import type { RouteRecordRaw } from 'vue-router/auto'

export const redirects: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'index',
    redirect: to => {
      const userData = useCookie<Record<string, unknown> | null | undefined>('userData')
      const userRole = userData.value?.role

      if (userRole === 'admin' || userRole === 'superadmin')
        return { name: 'attendance-dashboard' }

      return { name: 'attendance-login', query: to.query }
    },
  },
]

export const routes: RouteRecordRaw[] = []
