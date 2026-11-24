import type { Rule } from '@/plugins/casl/ability'

export function attendanceRoleToCaslRules(role: string | undefined | null): Rule[] {
  if (role === 'superadmin')
    return [{ action: 'manage', subject: 'all' }]

  if (role === 'admin') {
    return [
      { action: 'manage', subject: 'all' },
      { action: 'manage', subject: 'AuditLog', inverted: true },
    ]
  }

  if (role === 'user') {
    return [
      { action: 'manage', subject: 'all' },
      { action: 'manage', subject: 'User', inverted: true },
      { action: 'manage', subject: 'AuditLog', inverted: true },
      { action: 'manage', subject: 'Payroll', inverted: true },
      { action: 'manage', subject: 'Shift', inverted: true },
      { action: 'manage', subject: 'StaffAdmin', inverted: true },
    ]
  }

  return [{ action: 'read', subject: 'all' }]
}
