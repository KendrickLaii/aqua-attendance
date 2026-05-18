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
    title: 'User Management',
    icon: { icon: 'ri-admin-line' },
    to: 'attendance-users',
    action: 'manage',
    subject: 'User',
  },
]
