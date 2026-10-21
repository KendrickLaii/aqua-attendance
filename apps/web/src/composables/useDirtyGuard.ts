// Tracks unsaved edits on draft document editors. confirmDiscard() returns
// true when it is safe to switch selection / close / leave the route.
import { onBeforeRouteLeave } from 'vue-router'

export function useDirtyGuard(message = 'You have unsaved changes. Discard them?') {
  const dirty = ref(false)

  onBeforeRouteLeave(() => {
    // eslint-disable-next-line no-alert
    if (dirty.value && !window.confirm(message))
      return false
  })

  function confirmDiscard(): boolean {
    // eslint-disable-next-line no-alert
    return !dirty.value || window.confirm(message)
  }

  function markClean() {
    dirty.value = false
  }

  return { dirty, confirmDiscard, markClean }
}
