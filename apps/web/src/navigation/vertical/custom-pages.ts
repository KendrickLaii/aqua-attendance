export default [
  {
    title: 'Dashboard',
    icon: { icon: 'ri-dashboard-line' },
    to: 'attendance-dashboard',
  },
  {
    title: 'My QR Code',
    icon: { icon: 'ri-qr-code-line' },
    to: 'attendance-my-qr',
  },
  {
    title: 'Attendance Log',
    icon: { icon: 'ri-list-check' },
    to: 'attendance-log',
  },
  {
    title: 'User Management',
    icon: { icon: 'ri-group-line' },
    to: 'attendance-users',
    action: 'manage',
    subject: 'User',
  },
]
