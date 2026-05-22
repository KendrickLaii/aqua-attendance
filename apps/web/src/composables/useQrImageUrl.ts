import type { Ref } from 'vue'
import { toQrDataUrl } from '@/utils/qrCodeDataUrl'

/** Reactive QR preview image from a JWT/token string. */
export function useQrImageUrl(token: Ref<string>, sizePx = 280) {
  const qrImageUrl = ref('')
  const qrImageError = ref(false)
  const qrImageLoading = ref(false)

  watch(
    token,
    async (value) => {
      if (!value) {
        qrImageUrl.value = ''
        qrImageError.value = false
        qrImageLoading.value = false
        return
      }
      qrImageLoading.value = true
      try {
        qrImageUrl.value = await toQrDataUrl(value, sizePx)
        qrImageError.value = false
      }
      catch {
        qrImageUrl.value = ''
        qrImageError.value = true
      }
      finally {
        qrImageLoading.value = false
      }
    },
    { immediate: true },
  )

  return { qrImageUrl, qrImageError, qrImageLoading }
}
