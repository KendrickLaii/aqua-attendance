import appsAndPages from './apps-and-pages'
import charts from './charts'
import dashboard from './dashboard'
import forms from './forms'
import others from './others'
import uiElements from './ui-elements'

// comsec
import customPages from './custom-pages'
import type { VerticalNavItems } from '@layouts/types'

// dev
const devNavItems = [...dashboard, ...appsAndPages, ...uiElements, ...forms, ...charts, ...others]

// export default devNavItems as VerticalNavItems

// prod
const prodNavItems = import.meta.env.VITE_ENV_MODE === 'all' ? [...devNavItems, ...customPages] : import.meta.env.VITE_ENV_MODE === 'dev' ? [...customPages] : [...customPages]
export default prodNavItems as VerticalNavItems

/** from nav items collect all route name, for router guard to check "allowed" pages */
function collectRouteNames(
  items: Array<{ to?: string | { name?: string; path?: string }; children?: unknown[] }>,
  out: Set<string>,
) {
  for (const item of items) {
    if (typeof item.to === 'string')
      out.add(item.to)
    else if (item.to && typeof item.to === 'object' && item.to.name)
      out.add(item.to.name)
    if (Array.isArray(item.children) && item.children.length)
      collectRouteNames(item.children as Parameters<typeof collectRouteNames>[0], out)
  }
}

export interface NavFeatureFlags {
  inventory: boolean
}

function navTargetStartsWith(to: unknown, prefix: string): boolean {
  if (typeof to === 'string')
    return to.startsWith(prefix)

  if (to && typeof to === 'object') {
    const named = to as { name?: string; path?: string }
    if (typeof named.name === 'string' && named.name.startsWith(prefix))
      return true
    if (typeof named.path === 'string' && named.path.startsWith(prefix))
      return true
  }

  return false
}

function itemOrDescendantStartsWith(item: { to?: unknown; children?: unknown[] }, prefix: string): boolean {
  if (navTargetStartsWith(item.to, prefix))
    return true

  if (Array.isArray(item.children))
    return item.children.some(child => itemOrDescendantStartsWith(child as typeof item, prefix))

  return false
}

/** drop top-level nav groups gated behind a disabled runtime feature flag */
export function filterNavByFeatures(items: VerticalNavItems, flags: NavFeatureFlags): VerticalNavItems {
  if (flags.inventory)
    return items

  return items.filter(item => !itemOrDescendantStartsWith(item as { to?: unknown; children?: unknown[] }, 'attendance-inventory'))
}

/** return the set of route names that are allowed in the prod navigation, pages not in the set should be redirected to 404 */
export function getAllowedRouteNames(): Set<string> {
  const set = new Set<string>()

  collectRouteNames(prodNavItems as Parameters<typeof collectRouteNames>[0], set)

  return set
}
