const DEFAULT_ALERT_TIMEOUT_MS = 8000

function isActiveAlert(value: unknown) {
  if (value == null || value === false)
    return false
  if (typeof value === 'string')
    return value.trim() !== ''

  return true
}

function clearedAlertValue(value: unknown) {
  if (typeof value === 'string')
    return ''

  return null
}

/** Auto-dismiss page alerts (string or object refs) after a timeout. */
export function useAutoClearAlerts(
  ...sources: Ref<unknown>[]
) {
  const timers = new Map<number, ReturnType<typeof setTimeout>>()

  sources.forEach((source, index) => {
    watch(source, value => {
      const existing = timers.get(index)
      if (existing)
        clearTimeout(existing)

      if (!isActiveAlert(value)) {
        timers.delete(index)

        return
      }

      timers.set(index, setTimeout(() => {
        source.value = clearedAlertValue(value)
        timers.delete(index)
      }, DEFAULT_ALERT_TIMEOUT_MS))
    })
  })

  onUnmounted(() => {
    for (const timer of timers.values())
      clearTimeout(timer)
    timers.clear()
  })
}
