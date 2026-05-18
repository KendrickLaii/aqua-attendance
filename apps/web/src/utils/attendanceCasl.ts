import type { Rule } from '@/plugins/casl/ability'

export function attendanceRoleToCaslRules(role: string | undefined | null): Rule[] {
  if (role === 'superadmin')
    return [{ action: 'manage', subject: 'all' }]

  if (role === 'admin')
    return [{ action: 'manage', subject: 'all' }]

  return [{ action: 'read', subject: 'all' }]
}
