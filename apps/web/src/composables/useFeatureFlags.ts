import { ofetch } from 'ofetch'
import { readonly, ref } from 'vue'

export interface FeatureFlags {
  inventory: boolean
}

const apiBase = String(import.meta.env.VITE_ATTENDANCE_API_URL || 'http://localhost:8000/api').replace(/\/$/, '')

const featureFlags = ref<FeatureFlags>({ inventory: false })

let loadPromise: Promise<void> | null = null

export function loadFeatureFlags(): Promise<void> {
  if (!loadPromise) {
    loadPromise = ofetch<{ inventory?: boolean }>(`${apiBase}/features`)
      .then(data => {
        featureFlags.value = { inventory: !!data?.inventory }
      })
      .catch(() => {
        featureFlags.value = { inventory: false }
      })
  }

  return loadPromise
}

export function useFeatureFlags() {
  return {
    featureFlags: readonly(featureFlags),
    loadFeatureFlags,
  }
}
