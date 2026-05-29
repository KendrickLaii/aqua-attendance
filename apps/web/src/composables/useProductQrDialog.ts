import { getQRToken, refreshQRToken } from '@/api/attendance/events'
import type { Product } from '@/api/attendance/products'
import { useQrImageUrl } from '@/composables/useQrImageUrl'
import { copyToClipboard } from '@/utils/copyToClipboard'
import { formatApiError } from '@/utils/formatApiDetail'

const SCAN_TOKEN_SESSION_KEY = 'attendance-scan-token'
export const PRODUCT_QR_IMAGE_SIZE = 300

export function useProductQrDialog(options?: {
  qrSize?: number
  onRotated?: () => void | Promise<void>
}) {
  const router = useRouter()
  const qrSize = options?.qrSize ?? PRODUCT_QR_IMAGE_SIZE

  const qrDialog = ref(false)
  const qrProduct = ref<Product | null>(null)
  const qrToken = ref('')
  const qrError = ref('')
  const qrLoading = ref(false)
  const rotateConfirmOpen = ref(false)
  const rotating = ref(false)
  const rotateError = ref('')
  const copied = ref(false)
  const copyFailOpen = ref(false)
  let copiedHideTimer: ReturnType<typeof setTimeout> | null = null

  const { qrImageUrl, qrImageError, qrImageLoading } = useQrImageUrl(qrToken, qrSize)

  async function openQR(p: Product) {
    qrProduct.value = p
    qrLoading.value = true
    qrToken.value = ''
    qrError.value = ''
    qrDialog.value = true
    try {
      const data = await getQRToken(p.id)

      qrToken.value = data.qr_token
    }
    catch (e: unknown) {
      qrToken.value = ''
      qrError.value = formatApiError(e, 'Failed to load QR token')
    }
    finally {
      qrLoading.value = false
    }
  }

  function openRotateConfirm() {
    rotateError.value = ''
    rotateConfirmOpen.value = true
  }

  function closeRotateConfirm() {
    rotateConfirmOpen.value = false
    rotateError.value = ''
  }

  async function confirmRotate() {
    if (!qrProduct.value)
      return
    rotating.value = true
    rotateError.value = ''
    try {
      const data = await refreshQRToken(qrProduct.value.id)

      qrToken.value = data.qr_token
      qrProduct.value = { ...qrProduct.value, qr_token_version: data.token_version }
      closeRotateConfirm()
      await options?.onRotated?.()
    }
    catch (e: unknown) {
      rotateError.value = formatApiError(e, 'Could not rotate QR code')
    }
    finally {
      rotating.value = false
    }
  }

  async function copyQrToken() {
    if (!qrToken.value)
      return
    const ok = await copyToClipboard(qrToken.value)
    if (ok) {
      copyFailOpen.value = false
      copied.value = true
      if (copiedHideTimer)
        clearTimeout(copiedHideTimer)
      copiedHideTimer = setTimeout(() => {
        copied.value = false
      }, 2500)
    }
    else {
      copied.value = false
      copyFailOpen.value = true
    }
  }

  function selectTokenField(ev: FocusEvent) {
    const el = ev.target as HTMLInputElement | null

    el?.select()
  }

  function openWebScanner() {
    if (qrToken.value && typeof sessionStorage !== 'undefined')
      sessionStorage.setItem(SCAN_TOKEN_SESSION_KEY, qrToken.value)
    qrDialog.value = false
    router.push({ name: 'attendance-scanner' })
  }

  return {
    qrDialog,
    qrProduct,
    qrToken,
    qrError,
    qrLoading,
    rotateConfirmOpen,
    rotating,
    rotateError,
    copied,
    copyFailOpen,
    qrImageUrl,
    qrImageError,
    qrImageLoading,
    qrSize,
    openQR,
    openRotateConfirm,
    closeRotateConfirm,
    confirmRotate,
    copyQrToken,
    selectTokenField,
    openWebScanner,
  }
}
