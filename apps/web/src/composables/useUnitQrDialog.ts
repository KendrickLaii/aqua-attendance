import { getQRToken, refreshQRToken } from '@/api/attendance/events'
import type { Unit } from '@/api/attendance/units'
import { useQrImageUrl } from '@/composables/useQrImageUrl'
import { copyToClipboard } from '@/utils/copyToClipboard'
import { formatApiError } from '@/utils/formatApiDetail'
import { SCAN_ENTRY_SESSION_KEY, SCAN_TOKEN_SESSION_KEY } from '@/utils/attendanceSession'

export const UNIT_QR_IMAGE_SIZE = 300

export function useUnitQrDialog(options?: {
  qrSize?: number
  onRotated?: () => void | Promise<void>
}) {
  const router = useRouter()
  const qrSize = options?.qrSize ?? UNIT_QR_IMAGE_SIZE

  const qrDialog = ref(false)
  const qrUnit = ref<Unit | null>(null)
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

  async function openQR(p: Unit) {
    qrUnit.value = p
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
    if (!qrUnit.value)
      return
    rotating.value = true
    rotateError.value = ''
    try {
      const data = await refreshQRToken(qrUnit.value.id)

      qrToken.value = data.qr_token
      qrUnit.value = { ...qrUnit.value, qr_token_version: data.token_version }
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
    if (typeof sessionStorage !== 'undefined') {
      if (qrToken.value)
        sessionStorage.setItem(SCAN_TOKEN_SESSION_KEY, qrToken.value)
      sessionStorage.setItem(SCAN_ENTRY_SESSION_KEY, '1')
    }
    qrDialog.value = false
    router.push({ name: 'attendance-scanner' })
  }

  return {
    qrDialog,
    qrUnit,
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
