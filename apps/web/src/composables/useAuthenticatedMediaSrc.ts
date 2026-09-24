import { fetchUploadObjectUrl } from '@/api/attendance/uploads'
import { needsAuthenticatedMediaFetch, resolveMediaUrl } from '@/utils/mediaUrl'

/**
 * <img src> for stored media. Upload files are public UUID URLs, so this
 * resolves them to an address the browser can load without a Bearer token.
 */
export function useAuthenticatedMediaSrc(url: MaybeRefOrGetter<string | null | undefined>) {
  const src = ref('')
  let objectUrl = ''

  function revoke() {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = ''
    }
  }

  watch(
    () => toValue(url),
    async value => {
      const requestId = value ?? ''
      revoke()
      const resolved = resolveMediaUrl(value)
      if (!resolved) {
        src.value = ''
        return
      }
      if (!needsAuthenticatedMediaFetch(resolved)) {
        src.value = resolved
        return
      }
      try {
        const next = await fetchUploadObjectUrl(resolved)
        if ((toValue(url) ?? '') !== requestId) {
          URL.revokeObjectURL(next)
          return
        }
        objectUrl = next
        src.value = next
      }
      catch {
        if ((toValue(url) ?? '') === requestId)
          src.value = resolved
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(revoke)

  return src
}
