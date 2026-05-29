<template>
  <div class="dialog-footer">
    <slot />
  </div>
</template>

<style scoped lang="scss">
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;

  :deep(.v-btn) {
    height: 36px;
    min-height: 36px;
    padding-inline: 16px;
    font-size: 0.875rem;
    letter-spacing: normal;
  }
}
</style>
