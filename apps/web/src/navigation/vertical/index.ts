import type { VerticalNavItems } from '@layouts/types'
import appsAndPages from './apps-and-pages'
import charts from './charts'
import dashboard from './dashboard'
import forms from './forms'
import others from './others'
import uiElements from './ui-elements'

//comsec
import customPages from './custom-pages'

//dev
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

/** return the set of route names that are allowed in the prod navigation, pages not in the set should be redirected to 404 */
export function getAllowedRouteNames(): Set<string> {
  const set = new Set<string>()
  collectRouteNames(prodNavItems as Parameters<typeof collectRouteNames>[0], set)
  return set
}
