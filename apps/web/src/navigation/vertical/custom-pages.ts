export default [
  {
    title: 'Dashboard',
    icon: { icon: 'ri-dashboard-line' },
    to: 'attendance-dashboard',
  },
  {
    title: 'Product Management',
    icon: { icon: 'ri-group-line' },
    to: 'attendance-products',
  },
  {
    title: 'QR Codes',
    icon: { icon: 'ri-qr-code-line' },
    to: 'attendance-qr-codes',
  },
  {
    title: 'Attendance Log',
    icon: { icon: 'ri-list-check' },
    to: 'attendance-log',
  },
  {
    title: 'Summaries',
    icon: { icon: 'ri-calendar-todo-line' },
    to: 'attendance-summaries',
  },
  {
    title: 'Payroll',
    icon: { icon: 'ri-money-cny-circle-line' },
    to: 'attendance-payroll',
  },
  {
    title: 'Notifications',
    icon: { icon: 'ri-notification-3-line' },
    to: 'attendance-notifications',
  },
  {
    title: 'Audit Logs',
    icon: { icon: 'ri-shield-keyhole-line' },
    to: 'attendance-audit-logs',
    action: 'manage',
    subject: 'AuditLog',
  },
  {
    title: 'Location Management',
    icon: { icon: 'ri-map-pin-line' },
    to: 'attendance-locations',
  },
  {
    title: 'User Management',
    icon: { icon: 'ri-admin-line' },
    to: 'attendance-users',
    action: 'manage',
    subject: 'User',
  },
]
