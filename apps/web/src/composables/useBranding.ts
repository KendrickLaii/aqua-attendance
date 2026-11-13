import { ofetch } from 'ofetch'
import { h, readonly, ref } from 'vue'
import type { useTheme } from 'vuetify'
import { resolveBrand } from '@/config/brands'
import type { Brand } from '@/config/brands'
import { layoutConfig } from '@layouts'
import type { VerticalNavItems } from '@layouts/types'

const apiBase = String(import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api').replace(/\/$/, '')

const brand = ref<Brand>(resolveBrand('aqua'))

let loadPromise: Promise<void> | null = null

/** Push the resolved brand into static template values (document title, navbar title/logo). */
function applyBrandToShell() {
  document.title = brand.value.title

  // layoutConfig is the non-reactive source VerticalNav reads for the navbar
  // header; it re-renders when the brand-aware navItems prop changes. Leave it
  // untouched for aqua so the navbar keeps rendering the themeConfig default
  // ('aqua', CSS-uppercased) exactly as before.
  if (brand.value.key !== 'aqua') {
    layoutConfig.app.title = brand.value.title.toLowerCase() as Lowercase<string>
    layoutConfig.app.logo = h('img', { src: brand.value.logo, style: 'height: 30px; width: auto;' })
  }
}

export function loadBranding(): Promise<void> {
  if (!loadPromise) {
    loadPromise = ofetch<{ brand?: string }>(`${apiBase}/branding`)
      .then(data => {
        brand.value = resolveBrand(data?.brand)
        applyBrandToShell()
      })
      .catch(() => {
        // API unreachable (offline dev, pre-deploy) → keep the aqua default
        brand.value = resolveBrand('aqua')
      })
  }

  return loadPromise
}

/**
 * Override Vuetify `primary` for every declared theme (aqua / light / dark).
 * `themes` is a ref holding a plain record, so replace each theme object to
 * let the change propagate.
 */
export function applyBrandPrimaryColor(theme: ReturnType<typeof useTheme>, color: string) {
  const updated = { ...theme.themes.value }

  for (const [name, def] of Object.entries(updated)) {
    updated[name] = {
      ...def,
      colors: { ...(def.colors ?? {}), primary: color },
    }
  }

  theme.themes.value = updated
}

export function useBranding() {
  /** Label override: `terms[key] ?? key` */
  const t = (key: string) => brand.value.terms[key] ?? key

  /** Nav item title override: `terms['nav:<original>'] ?? original` */
  const navTitle = (original: string) => brand.value.terms[`nav:${original}`] ?? original

  /** Recursively map nav item titles through `navTitle` (terms are brand-scoped). */
  const applyNavTitles = (items: VerticalNavItems): VerticalNavItems => {
    return items.map(item => {
      if ('heading' in item)
        return item

      return {
        ...item,
        title: navTitle(item.title),
        ...('children' in item && item.children?.length
          ? { children: applyNavTitles(item.children) }
          : {}),
      } as typeof item
    })
  }

  return {
    brand: readonly(brand),
    loadBranding,
    t,
    navTitle,
    applyNavTitles,
  }
}
