<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useToast } from '@/composables/useToast'

const { toasts, dismiss } = useToast()

const remainingMsById = reactive<Record<number, number>>({})
const pausedById = reactive<Record<number, boolean>>({})
const lastTickAt = ref<number>(Date.now())
let timer: number | undefined

function formatCloseIn(ms: number) {
  const s = Math.max(0, ms) / 1000
  if (s >= 10)
    return `${Math.ceil(s)}s`
  return `${s.toFixed(1)}s`
}

function pauseToast(id: number) {
  pausedById[id] = true
  lastTickAt.value = Date.now()
}

function resumeToast(id: number) {
  pausedById[id] = false
  lastTickAt.value = Date.now()
}

function tick() {
  const now = Date.now()
  const delta = now - lastTickAt.value
  if (delta < 0)
    return
  lastTickAt.value = now

  // Update all current toasts
  for (const toast of toasts.value) {
    const id = toast.id
    if (pausedById[id])
      continue

    if (remainingMsById[id] === undefined)
      remainingMsById[id] = toast.duration

    remainingMsById[id] -= delta
    if (remainingMsById[id] <= 0) {
      dismiss(id)
      delete remainingMsById[id]
      delete pausedById[id]
    }
  }

  // Cleanup maps for removed toasts
  for (const idStr of Object.keys(remainingMsById)) {
    const id = Number(idStr)
    if (!toasts.value.some(t => t.id === id)) {
      delete remainingMsById[id]
      delete pausedById[id]
    }
  }
}

onMounted(() => {
  lastTickAt.value = Date.now()
  timer = window.setInterval(tick, 100)
})

onBeforeUnmount(() => {
  if (timer)
    window.clearInterval(timer)
})
</script>

<template>
  <Teleport to="body">
    <div class="toast-stack">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          :class="`bg-${toast.color}`"
          @mouseenter="pauseToast(toast.id)"
          @mouseleave="resumeToast(toast.id)"
          @click="dismiss(toast.id)"
        >
          <div class="toast-main">
            <VIcon
              :icon="toast.color === 'error' ? 'ri-close-circle-line' : 'ri-checkbox-circle-line'"
              size="small"
              class="mr-2"
            />
            <span class="toast-message">{{ toast.message }}</span>
          </div>

          <!-- bottom line: show close countdown -->
          <div class="toast-footer">
            <div class="toast-progress">
              <div
                class="toast-progress-bar"
                :style="{
                  width: `${Math.max(0, Math.min(1, (remainingMsById[toast.id] ?? toast.duration) / toast.duration)) * 100}%`
                }"
              />
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  padding: 10px 20px;
  border-radius: 8px;
  color: white;
  font-size: 0.875rem;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  pointer-events: auto;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  min-width: 200px;
  max-width: 400px;
  white-space: normal;
  overflow-wrap: anywhere;
}

.toast-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toast-message {
  line-height: 1.2;
  white-space: pre-line;
}

.toast-footer {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.toast-progress {
  width: 100%;
  height: 2px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 999px;
  overflow: hidden;
}

.toast-progress-bar {
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  transition: width 0.1s linear;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
