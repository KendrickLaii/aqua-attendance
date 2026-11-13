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
export interface Brand {
  key: string
  title: string // document.title / navbar app title
  loginTitle: string // heading on the attendance login page
  footerName: string // "Made with ❤ by <footerName>"
  logo: string // image URL used for the navbar logo
  primaryColor?: string // optional override for Vuetify `primary`
  hiddenRoutes: string[] // route name prefixes hidden from nav + blocked in guards
  terms: Record<string, string> // label overrides; `nav:<title>` keys rename nav items
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
  },
  cpa: {
    key: 'cpa',
    title: 'CPA Attendance',
    loginTitle: 'CPA Attendance',
    footerName: 'CPA',

    // TODO: replace with the real CPA logo once the client provides assets
    logo: aquaLogo,
    primaryColor: '#1565C0', // placeholder until the client confirms a palette
    hiddenRoutes: [],
    terms: {},
  },
}

/** Unknown brand keys (typos, stale env) fall back to aqua. */
export function resolveBrand(key: string | undefined | null): Brand {
  return brands[key ?? 'aqua'] ?? brands.aqua
}
