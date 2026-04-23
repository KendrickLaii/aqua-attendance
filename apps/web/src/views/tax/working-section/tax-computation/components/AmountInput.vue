<script setup lang="ts">
const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
}>()

const isFocused = ref(false)
const rawValue = ref('')

watch(() => props.modelValue, val => {
  if (!isFocused.value) rawValue.value = formattedToRaw(val ?? '')
})

function formattedToRaw(v: string): string {
  const t = String(v ?? '').trim()
  if (!t || t === '-') return ''

  // (1,234) -> -1234 ; 1,234 -> 1234 ; -1234 -> -1234
  const isParenNegative = /^\(.*\)$/.test(t)
  const stripped = t.replace(/[(),\s]/g, '')
  const numeric = isParenNegative ? `-${stripped}` : stripped
  const n = Number(numeric)
  return Number.isNaN(n) || n === 0 ? '' : String(n)
}

function rawToFormatted(v: string): string {
  const stripped = String(v ?? '').replace(/,/g, '').trim()
  if (!stripped) return '-'
  const n = Number(stripped)
  if (Number.isNaN(n) || n === 0) return '-'
  const abs = Math.abs(n).toLocaleString('en-US')
  return n < 0 ? `(${abs})` : abs
}

// What the input displays
const displayValue = computed(() =>
  isFocused.value ? rawValue.value : (props.modelValue?.trim() ? props.modelValue : '-'),
)

const onFocus = () => {
  isFocused.value = true
  rawValue.value = formattedToRaw(props.modelValue ?? '')
}

const onBlur = () => {
  isFocused.value = false
  // Store formatted value in v-model
  const formatted = rawToFormatted(rawValue.value)
  rawValue.value = formattedToRaw(formatted)
  emit('update:modelValue', formatted)
}

const onInput = (val: string) => {
  // Only allow digits and minus while typing
  rawValue.value = val.replace(/[^\d-]/g, '')
}

// Init
rawValue.value = formattedToRaw(props.modelValue ?? '')
</script>

<template>
  <VTextField
    :model-value="displayValue"
    density="compact"
    hide-details
    variant="outlined"
    class="pat-amount-input"
    @focus="onFocus"
    @blur="onBlur"
    @update:model-value="onInput"
  />
</template>
