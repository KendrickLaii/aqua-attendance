import aquaLogo from '@images/logos/aqua-logo.png'

/**
 * Runtime per-brand registry.
 *
 * The API serves `GET /api/branding` → `{ brand: <key> }` (env `APP_BRAND`),
 * letting the SAME web image present a different brand per server.
 * `aqua` is the production look and must stay identical to before this
 * mechanism existed; `cpa` is a placeholder for the demo server — real
 * logo / wordings come later from the client.
 */
/** Which tuition-invoice print layout this brand uses. Credit notes stay on the shared layout. */
export type InvoicePrintTemplate = 'aqua' | 'debit-note'

export interface Brand {
  key: string
  title: string // document.title / navbar app title
  loginTitle: string // heading on the attendance login page
  footerName: string // "Made with ❤ by <footerName>"
  logo: string // image URL used for the navbar logo
  primaryColor?: string // optional override for Vuetify `primary`
  hiddenRoutes: string[] // route name prefixes hidden from nav + blocked in guards
  terms: Record<string, string> // label overrides; `nav:<title>` keys rename nav items
  manualInvoiceDefaultLines: number // blank rows on a new manual invoice
  manualInvoiceMaxLines: number
  invoicePrintTemplate: InvoicePrintTemplate
}

export const brands: Record<string, Brand> = {
  aqua: {
    key: 'aqua',
    title: 'AQUA Attendance',
    loginTitle: 'AQUA Attendance',
    footerName: 'AQUA',
    logo: aquaLogo,
    hiddenRoutes: [],
    terms: {},
    manualInvoiceDefaultLines: 1,
    manualInvoiceMaxLines: 5,
    invoicePrintTemplate: 'aqua',
  },
  cpa: {
    key: 'cpa',
    title: 'AQUA ERP',
    loginTitle: 'AQUA ERP',
    footerName: 'AQUA ERP',

    // TODO: replace with the real CPA logo once the client provides assets
    logo: aquaLogo,
    primaryColor: '#1565C0', // placeholder until the client confirms a palette
    hiddenRoutes: [],
    terms: {
      'nav:Courses': 'Services',
      'Course Management': 'Service Management',
      'Add Course': 'Add Service',
      'Courses': 'Services',
      'course': 'service',
      'courses': 'services',
      'Add course': 'Add service',
      'Edit course': 'Edit service',
      'Active course': 'Active service',
      'Subject': 'Group',
      'Chinese name': 'Name',
      'English name': 'Sub-name',
      'Campus': 'Team',
      'Teacher / staff': 'staff',
      'Class Offerings': 'Line items',
      'Class offerings': 'Line items',
      'Add Class': 'Add Line item',
      'Add class': 'Add line item',
      'Edit class': 'Edit line item',
      'Class code': 'Line item code',
      'Class days': 'Line item days',
      'Active class': 'Active line item',
      'class': 'line item',
      'classes': 'line items',
      'Class': 'Line item',
      'Classes': 'Line items',
      'class offering': 'line item',
      'class offerings': 'line items',
      'In class': 'In line item',
      'in class': 'in line item',
      'Join class': 'Add to line item',
      'Leave class': 'Remove from line item',
      'Back in class': 'Back on line item',
      'back in class': 'back on line item',
      'Jump to class': 'Jump to line item',
      'Class roster · 班次名冊': 'Recurring Service',
      'Join a student': 'Enrollment',
      'Student': 'Client',
      'Find student': 'Find Client',
      'Tuition invoices': 'Invoices',
      'Location': 'Team',
      'nav:Location Management': 'Team Management',
      'Location Management': 'Team Management',
      'Add Location': 'Add Team',
      'Create Location': 'Create Team',
      'location': 'team',
      'locations': 'teams',
      'Search locations...': 'Search teams...',
      'No locations match your filters.': 'No teams match your filters.',
      'Failed to load locations. Please try again.': 'Failed to load teams. Please try again.',
      'Could not save location': 'Could not save team',
      'Could not delete location': 'Could not delete team',
      'Locations referenced by attendance records cannot be deleted.': 'Teams referenced by attendance records cannot be deleted.',
      'All locations': 'All Teams',
      'Tutor': 'Staff',
      'Student name': 'Client',
      'Search student name or code — or type any name…': 'Search client name or code — or type any name…',
      'Location (logo)': 'Team',
      'Tutor for this bill — for commission…': 'Staff for this bill — for commission…',
      'Pick a student, or type a name for a walk-in invoice.': 'Pick a client, or type a name for a walk-in invoice.',
      'Please select a location for the manual invoice.': 'Please select a team for the manual invoice.',
      'Month': 'Period',
      'Bill month': 'Period',
      'Month this bill counts in': 'Period this bill counts in',
      'Add a class': 'Add Item',
      'Search student…': 'Search client…',
      'No issued invoices to collect for this student.': 'No issued invoices to collect for this client.',
      'Student, receipt no., paid by…': 'Client, receipt no., paid by…',
      'Could not load students.': 'Could not load clients.',
      'Pick a location.': 'Pick a team.',
      'Could not load locations. Campus filter and print headers may be incomplete.': 'Could not load teams. Team filter and print headers may be incomplete.',
      'rosterStatusActive': 'Active',
      'rosterStatusInactive': 'Inactive',
      'Pick a class to open its roll': 'Pick a line item to open its roll',
      'No class selected': 'No line item selected',
      'Click a class above, or search by code in Jump to class.': 'Click a line item above, or search by code in Jump to line item.',
    },
    manualInvoiceDefaultLines: 1,
    manualInvoiceMaxLines: 100,
    invoicePrintTemplate: 'debit-note',
  },
}

/** Unknown brand keys (typos, stale env) fall back to aqua. */
export function resolveBrand(key: string | undefined | null): Brand {
  return brands[key ?? 'aqua'] ?? brands.aqua
}
