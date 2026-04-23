import apps from './apps'
import charts from './charts'
import dashboard from './dashboard'
import forms from './forms'
import others from './others'
import pages from './pages'
import tables from './tables'
import uiElements from './ui-elements'
import customPages from './custom-pages'
import type { HorizontalNavItems } from '@layouts/types'

const devNavItems = [...dashboard, ...apps, ...pages, ...uiElements, ...forms, ...tables, ...charts, ...others] as HorizontalNavItems
// export default devNavItems

// prod
// const prodNavItems = [...devNavItems, ...customPages]
const prodNavItems = [...customPages]
export default prodNavItems as HorizontalNavItems

/** from nav items collect all route name, for router guard or other checks to know which pages are \"opened\" in horizontal nav */
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

/** return the set of route names that are allowed in the horizontal navigation */
export function getAllowedRouteNames(): Set<string> {
  const set = new Set<string>()
  collectRouteNames(prodNavItems as Parameters<typeof collectRouteNames>[0], set)
  return set
}

