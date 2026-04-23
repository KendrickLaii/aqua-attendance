export default [
  {
    title: 'Client',
    icon: { icon: 'ri-account-box-line' },
    to: 'tax-clients',
  },
  {
    title: 'Job Management',
    icon: { icon: 'ri-todo-line' },
    to: 'tax-job-management',
  },
  {
    title: 'User',
    icon: { icon: 'ri-user-3-line' },
    to: 'tax-user',
    action: 'manage',
    subject: 'User',
  },
  {
    title: 'Working Section',
    icon: { icon: 'ri-id-card-line' },
    to: 'tax-working-section-list',
  },
  {
    title: 'Context',
    icon: { icon: 'ri-book-shelf-line' },
    children: [
      { title: 'Tax return field setup', to: { name: 'tax-context-tax-return-field-setup' } },
    ],
  },
  {
    title: 'Other Settings',
    icon: { icon: 'ri-settings-2-line' },
    children: [
      { title: 'Currency', to: { name: 'tax-other-settings-currency' } },
      { title: 'Business Nature', to: { name: 'tax-other-settings-business-nature' } },
      { title: 'Config', to: { name: 'tax-other-settings-config' } },
    ],
  },
  {
    title: 'AddOn',
    icon: { icon: 'ri-function-add-line' },
    to: 'tax-add-on',
  },
]
