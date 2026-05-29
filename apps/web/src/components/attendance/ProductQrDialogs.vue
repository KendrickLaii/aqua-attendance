<script setup lang="ts">
import { useDisplay } from 'vuetify'
import { PRODUCT_QR_IMAGE_SIZE, useProductQrDialog } from '@/composables/useProductQrDialog'

const emit = defineEmits<{
  rotated: []
}>()

const { smAndDown } = useDisplay()
const { width: windowWidth } = useWindowSize()

const {
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
  openQR,
  openRotateConfirm,
  closeRotateConfirm,
  confirmRotate,
  copyQrToken,
  selectTokenField,
  openWebScanner,
} = useProductQrDialog({
  onRotated: () => emit('rotated'),
})

const displayQrSize = computed(() => {
  if (smAndDown.value)
    return Math.min(PRODUCT_QR_IMAGE_SIZE, Math.floor(windowWidth.value * 0.72))

  return PRODUCT_QR_IMAGE_SIZE
})

function productTypeLabel(type: string | undefined) {
  if (type === 'staff')
    return 'Staff'
  if (type === 'student')
    return 'Student'

  return type ?? ''
}

defineExpose({ openQR })
</script>

<template>
  <!-- QR Code Dialog -->
  <AttendanceInfoDialog
    v-model="qrDialog"
    :title="qrProduct?.full_name"
    :subtitle="qrProduct ? `${qrProduct.code} · ${productTypeLabel(qrProduct.product_type)}` : undefined"
    icon="ri-qr-code-line"
    centered
    @action="qrDialog = false"
  >
    <div
      v-if="qrLoading"
      class="py-12"
    >
      <VProgressCircular
        indeterminate
        color="primary"
        size="48"
      />
    </div>
    <template v-else-if="qrToken">
      <div
        class="my-4 d-flex justify-center align-center"
        :style="{ minHeight: `${displayQrSize}px` }"
      >
        <VProgressCircular
          v-if="qrImageLoading"
          indeterminate
          color="primary"
          size="40"
        />
        <VAlert
          v-else-if="qrImageError"
          type="error"
          variant="tonal"
          density="compact"
        >
          Could not render QR image.
        </VAlert>
        <VImg
          v-else-if="qrImageUrl"
          :src="qrImageUrl"
          :width="displayQrSize"
          :height="displayQrSize"
          class="qr-dialog-image rounded"
        />
      </div>
      <div class="text-caption text-medium-emphasis mb-3">
        This QR stays valid until you rotate it. On scan, choose Check In or Check Out
        (mobile app or web scanner). Same code works every day.
      </div>
      <div class="d-flex justify-center flex-wrap gap-2 mb-2">
        <VBtn
          variant="tonal"
          size="small"
          color="primary"
          prepend-icon="ri-qr-scan-2-line"
          @click="openWebScanner"
        >
          Web scanner
        </VBtn>
        <VBtn
          variant="outlined"
          size="small"
          :prepend-icon="copied ? 'ri-check-line' : 'ri-file-copy-line'"
          :color="copied ? 'success' : undefined"
          @click="copyQrToken"
        >
          {{ copied ? 'Copied' : 'Copy token' }}
        </VBtn>
        <VBtn
          variant="text"
          size="small"
          color="warning"
          prepend-icon="ri-refresh-line"
          @click="openRotateConfirm"
        >
          Rotate QR
        </VBtn>
      </div>
      <VTextField
        :model-value="qrToken"
        readonly
        label="Raw token (tap to select, then copy)"
        density="compact"
        variant="outlined"
        class="text-start mt-4"
        hide-details
        @focus="selectTokenField"
      />
      <div class="text-caption text-disabled mt-2">
        Token version: {{ qrProduct?.qr_token_version }}
      </div>
    </template>
    <VAlert
      v-else
      type="error"
      variant="tonal"
    >
      {{ qrError || 'Failed to generate QR code' }}
    </VAlert>
  </AttendanceInfoDialog>

  <AttendanceConfirmDialog
    v-model="rotateConfirmOpen"
    :title="`Rotate QR for ${qrProduct?.full_name}?`"
    confirm-label="Rotate"
    confirm-color="warning"
    :loading="rotating"
    :error="rotateError"
    @confirm="confirmRotate"
    @cancel="closeRotateConfirm"
    @clear-error="rotateError = ''"
  >
    The current QR will stop working. Use this only if the printed
    code was lost or shared with someone who shouldn't have it.
  </AttendanceConfirmDialog>

  <VSnackbar
    v-model="copyFailOpen"
    color="error"
    location="bottom"
    :timeout="7000"
  >
    Could not copy automatically. Select the text in the field above and copy manually (Ctrl+C or long-press).
  </VSnackbar>
</template>

<style scoped lang="scss">
.qr-dialog-image {
  border: 4px solid rgb(var(--v-theme-primary));
  max-width: min(300px, 85vw);
  height: auto;
}
</style>
