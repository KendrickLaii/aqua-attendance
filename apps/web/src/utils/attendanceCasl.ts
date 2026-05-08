import type { Rule } from '@/plugins/casl/ability'

/** CASL rules for attendance layout + nav (User Management needs `manage` on `User` for admins). */
export function attendanceRoleToCaslRules(role: string | undefined | null): Rule[] {
  if (role === 'admin')
    return [{ action: 'manage', subject: 'all' }]

  return [{ action: 'read', subject: 'all' }]
}
