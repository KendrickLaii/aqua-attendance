import type { RouteRecordRaw } from 'vue-router/auto'

export const redirects: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'index',
    redirect: to => {
      const userData = useCookie<Record<string, unknown> | null | undefined>('userData')
      const userRole = userData.value?.role

      if (userRole === 'admin')
        return { name: 'attendance-dashboard' }
      if (userRole === 'staff')
        return { name: 'attendance-dashboard' }
      if (userRole === 'student')
        return { name: 'attendance-my-qr' }

      return { name: 'attendance-login', query: to.query }
    },
  },
]

export const routes: RouteRecordRaw[] = []
