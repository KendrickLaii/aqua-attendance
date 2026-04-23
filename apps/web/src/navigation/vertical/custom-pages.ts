export default [
  {
    title: 'Dashboard',
    icon: { icon: 'ri-dashboard-line' },
    to: 'attendance-dashboard',
  },
  {
    title: 'QR Scanner',
    icon: { icon: 'ri-qr-scan-2-line' },
    to: 'attendance-scanner',
  },
  {
    title: 'My QR Code',
    icon: { icon: 'ri-qr-code-line' },
    to: 'attendance-my-qr',
  },
  {
    title: 'Attendance Log',
    icon: { icon: 'ri-list-check-line' },
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
