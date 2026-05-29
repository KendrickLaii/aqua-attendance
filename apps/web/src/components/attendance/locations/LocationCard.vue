<script setup lang="ts">
import type { LocationItem } from '@/api/attendance/locations'
import { cardCoverUrl, formatCardBusinessHours, showCardIcon } from '@/utils/locationHours'

defineProps<{
  location: LocationItem
}>()

const emit = defineEmits<{
  edit: []
  delete: []
}>()
</script>

<template>
  <VCard
    class="location-card d-flex flex-column"
    hover
    height="100%"
    :class="{ 'location-card--inactive': !location.is_active }"
  >
    <div class="location-card__cover">
      <VImg
        v-if="cardCoverUrl(location)"
        :src="cardCoverUrl(location) || ''"
        height="128"
        cover
        class="location-card__cover-img"
      />
      <div
        v-else
        class="location-card__cover-placeholder"
      >
        <VIcon
          icon="ri-map-pin-line"
          size="40"
          color="primary"
        />
      </div>
      <VChip
        class="location-card__status"
        :color="location.is_active ? 'success' : 'grey'"
        size="small"
        variant="flat"
        label
      >
        {{ location.is_active ? 'Active' : 'Inactive' }}
      </VChip>
    </div>

    <VCardText class="location-card__body pa-4">
      <div class="location-card__header">
        <div class="min-w-0 flex-grow-1">
          <div
            class="location-card__title text-truncate"
            :title="location.name_en"
          >
            {{ location.name_en }}
          </div>
          <div
            v-if="location.name_zh"
            class="location-card__subtitle text-truncate"
            :title="location.name_zh"
          >
            {{ location.name_zh }}
          </div>
          <div
            v-if="location.code"
            class="location-card__code text-truncate"
          >
            {{ location.code }}
          </div>
        </div>
        <VAvatar
          v-if="showCardIcon(location)"
          size="36"
          rounded="lg"
          class="location-card__avatar flex-shrink-0"
        >
          <VImg
            :src="location.icon_url || ''"
            cover
          />
        </VAvatar>
      </div>

      <div
        v-if="location.location_type || location.region"
        class="location-card__chips"
      >
        <VChip
          v-if="location.location_type"
          size="x-small"
          color="primary"
          variant="tonal"
          label
        >
          {{ location.location_type }}
        </VChip>
        <VChip
          v-if="location.region"
          size="x-small"
          color="primary"
          variant="tonal"
          label
        >
          {{ location.region }}
        </VChip>
      </div>

      <div
        v-if="formatCardBusinessHours(location) || location.address"
        class="location-card__meta-block"
      >
        <div
          v-if="formatCardBusinessHours(location)"
          class="location-card__meta"
        >
          <VIcon
            icon="ri-time-line"
            size="15"
            class="location-card__meta-icon"
          />
          <span>{{ formatCardBusinessHours(location) }}</span>
        </div>
        <div
          v-if="location.address"
          class="location-card__meta"
        >
          <VIcon
            icon="ri-road-map-line"
            size="15"
            class="location-card__meta-icon"
          />
          <span class="location-card__address">{{ location.address }}</span>
        </div>
      </div>

      <div class="location-card__actions">
        <VBtn
          icon
          size="small"
          variant="text"
          color="default"
          title="Edit"
          :aria-label="`Edit ${location.name_en}`"
          @click="emit('edit')"
        >
          <VIcon icon="ri-edit-line" />
        </VBtn>
        <VBtn
          icon
          size="small"
          variant="text"
          color="error"
          title="Delete"
          :aria-label="`Delete ${location.name_en}`"
          @click="emit('delete')"
        >
          <VIcon icon="ri-delete-bin-line" />
        </VBtn>
      </div>
    </VCardText>
  </VCard>
</template>

<style scoped lang="scss">
.location-card {
  overflow: hidden;
  transition: box-shadow 0.2s ease;

  &--inactive {
    opacity: 0.72;
  }

  &__cover {
    position: relative;
    overflow: hidden;
  }

  &__cover-img {
    background: rgb(var(--v-theme-surface-variant));
  }

  &__cover-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 128px;
    background: rgba(var(--v-theme-primary), 0.06);
  }

  &__status {
    position: absolute;
    top: 10px;
    right: 10px;
    font-weight: 600;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  }

  &__body {
    display: flex;
    flex: 1;
    flex-direction: column;
  }

  &__header {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  &__title {
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.35;
  }

  &__subtitle {
    font-size: 0.8125rem;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
    line-height: 1.35;
    margin-top: 2px;
  }

  &__code {
    font-size: 0.75rem;
    color: rgba(var(--v-theme-on-surface), var(--v-disabled-opacity));
    margin-top: 2px;
  }

  &__avatar {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }

  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
  }

  &__meta-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 12px;
  }

  &__meta {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    font-size: 0.8125rem;
    line-height: 1.4;
    color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  }

  &__meta-icon {
    flex-shrink: 0;
    margin-top: 1px;
    opacity: 0.7;
  }

  &__address {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
    gap: 2px;
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  }
}
</style>
