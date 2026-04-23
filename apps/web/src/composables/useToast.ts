import { ref } from 'vue'

export interface ToastItem {
  id: number
  message: string
  color: string
  createdAt: number
  duration: number
}

// Module-level singleton so all components share the same toast list
const toasts = ref<ToastItem[]>([])
let _id = 0

export function useToast() {
  function show(message: string, color = 'success', duration = 3000) {
    const id = _id++
    toasts.value.push({ id, message, color, createdAt: Date.now(), duration })
  }

  function dismiss(id: number) {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx >= 0)
      toasts.value.splice(idx, 1)
  }

  return { toasts, show, dismiss }
}
