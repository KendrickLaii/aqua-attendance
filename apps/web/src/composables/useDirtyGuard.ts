// Tracks unsaved edits on draft document editors. confirmDiscard() resolves
// true when it is safe to switch selection / close / leave the route.
import { onBeforeRouteLeave } from 'vue-router'
import { useGlobalConfirm } from '@/composables/useGlobalConfirm'

export function useDirtyGuard(message = '未儲存的修改會消失。') {
  const dirty = ref(false)
  const { confirmDialog } = useGlobalConfirm()

  onBeforeRouteLeave(async () => {
    if (dirty.value && !(await confirmDiscard()))
      return false
  })

  async function confirmDiscard(): Promise<boolean> {
    if (!dirty.value)
      return true

    return confirmDialog({
      title: '放棄未儲存的修改？',
      message,
      confirmLabel: 'Discard',
      cancelLabel: 'Keep editing',
      tone: 'warning',
    })
  }

  function markClean() {
    dirty.value = false
  }

  return { dirty, confirmDiscard, markClean }
}
