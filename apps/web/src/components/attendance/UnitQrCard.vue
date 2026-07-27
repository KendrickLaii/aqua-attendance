<script setup lang="ts">
import { useIntersectionObserver } from '@vueuse/core'
import type { Unit } from '@/api/attendance/units'
import { getQRToken } from '@/api/attendance/events'
import { useQrImageUrl } from '@/composables/useQrImageUrl'
import { formatLastAttendance } from '@/utils/attendanceDisplay'
import { formatApiError } from '@/utils/formatApiDetail'
import { UNIT_QR_CARD_IMAGE_SIZE } from '@/utils/printUnitQrs'

const props = defineProps<{
  unit: Unit
}>()

const emit = defineEmits<{
  openDetail: []
}>()

const selected = defineModel<boolean>('selected', { default: false })

const cardRef = ref<HTMLElement | null>(null)
const token = ref('')
const loadError = ref('')
const loadingToken = ref(false)
const hasLoaded = ref(false)

const { qrImageUrl, qrImageError, qrImageLoading } = useQrImageUrl(token, UNIT_QR_CARD_IMAGE_SIZE)

async function loadQrToken() {
  if (hasLoaded.value || loadingToken.value)
    return

  loadingToken.value = true
  loadError.value = ''
  try {
    const data = await getQRToken(props.unit.id)

    token.value = data.qr_token
    hasLoaded.value = true
  }
  catch (e) {
    loadError.value = formatApiError(e, 'Failed to load QR')
  }
  finally {
    loadingToken.value = false
  }
}

useIntersectionObserver(
  cardRef,
  ([entry]) => {
    if (entry?.isIntersecting)
      loadQrToken()
  },
  { rootMargin: '120px' },
)

const showQrSpinner = computed(() => loadingToken.value || qrImageLoading.value)
const showQrError = computed(() => !!loadError.value || qrImageError.value)

function typeColor(type: string) {
  return type === 'staff' ? 'info' : 'success'
}

function typeLabel(type: string) {
  if (type === 'staff')
    return 'Staff'
  if (type === 'student')
    return 'Student'

  return type
}
</script>

<template>
  <div
    ref="cardRef"
    class="h-100"
  >
    <VCard
      class="qr-unit-card text-center h-100"
      variant="outlined"
    >
      <div class="qr-unit-card__select">
        <VCheckbox
          v-model="selected"
          density="compact"
          hide-details
          :aria-label="`Select ${unit.full_name}`"
          @click.stop
        />
      </div>

      <VCardText class="pt-8 pb-3">
        <div class="qr-unit-card__image-wrap d-flex justify-center align-center mx-auto mb-3">
          <VProgressCircular
            v-if="showQrSpinner"
            indeterminate
            color="primary"
            size="32"
          />
          <VAlert
            v-else-if="showQrError"
            type="error"
            variant="tonal"
            density="compact"
            class="text-caption px-2"
          >
            QR unavailable
          </VAlert>
          <VImg
            v-else-if="qrImageUrl"
            :src="qrImageUrl"
            :width="UNIT_QR_CARD_IMAGE_SIZE"
            :height="UNIT_QR_CARD_IMAGE_SIZE"
            class="qr-unit-card__image rounded"
            :alt="`QR code for ${unit.full_name}`"
          />
        </div>

        <div
          class="qr-unit-name text-subtitle-2 font-weight-bold"
          :title="unit.full_name"
        >
          {{ unit.full_name }}
        </div>
        <div class="text-body-2 text-medium-emphasis mb-2">
          {{ unit.code }}
        </div>
        <div class="d-flex justify-center gap-2 mb-2">
          <VChip
            :color="typeColor(unit.unit_type)"
            size="small"
            label
          >
            {{ typeLabel(unit.unit_type) }}
          </VChip>
        </div>
        <div
          class="text-caption"
          :class="unit.last_event_at && unit.attendance_status === 'checked_in' ? 'text-success' : 'text-medium-emphasis'"
        >
          {{ formatLastAttendance(unit, { compact: true }) }}
        </div>
      </VCardText>

      <VCardActions class="justify-center pt-0 pb-3">
        <VBtn
          variant="text"
          size="small"
          prepend-icon="ri-settings-3-line"
          @click.stop="emit('openDetail')"
        >
          Rotate / copy
        </VBtn>
      </VCardActions>
    </VCard>
  </div>
</template>

<style scoped lang="scss">
.qr-unit-card {
  position: relative;
  height: 100%;

  &__select {
    position: absolute;
    top: 4px;
    left: 4px;
    z-index: 1;
  }

  &__image-wrap {
    width: 152px;
    height: 152px;
  }

  &__image {
    border: 3px solid rgb(var(--v-theme-primary));
    max-width: 100%;
    height: auto;
  }
}

.qr-unit-name {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}
</style>
