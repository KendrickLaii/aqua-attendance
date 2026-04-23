<script setup lang="ts">
// Code example(parent component):
// const showDeleteConfirm = ref(false)
// <ConfirmDialog
//     v-model="showDeleteConfirm"
//     header="Confirm Delete"
//     text="Are you sure you want to delete this administrator?<br/>This action cannot be undone."
//     confirm-button-text="Delete"
//     confirm-button-color="error"
//     max-width="500"
//     use-html
//     @confirm="confirmDelete"
//     @cancel="cancelDelete"
// />
interface Props {
    modelValue: boolean
    header?: string
    text?: string
    confirmButtonText?: string
    confirmButtonColor?: string
    maxWidth?: string
    useHtml?: boolean
}

const props = withDefaults(defineProps<Props>(), {
    header: 'Confirm',
    text: 'Are you sure you want to proceed?',
    confirmButtonText: 'Confirm',
    confirmButtonColor: 'primary',
    maxWidth: '400',
    useHtml: false,
})

interface Emit {
    (e: 'update:modelValue', value: boolean): void
    (e: 'confirm'): void
    (e: 'cancel'): void
}

const emit = defineEmits<Emit>()

const isVisible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value),
})

const handleConfirm = () => {
    emit('confirm')
    isVisible.value = false
}

const handleCancel = () => {
    emit('cancel')
    isVisible.value = false
}

// ESC key to cancel
const onEscape = (e: KeyboardEvent) => {
    if (e.key === 'Escape') handleCancel()
}
// Enter / Space to confirm
const onConfirmKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        handleConfirm()
    }
}
watch(isVisible, (visible) => {
    if (visible) {
        document.addEventListener('keydown', onEscape)
        document.addEventListener('keydown', onConfirmKey)
    } else {
        document.removeEventListener('keydown', onEscape)
        document.removeEventListener('keydown', onConfirmKey)
    }
}, { immediate: true })
onBeforeUnmount(() => {
    document.removeEventListener('keydown', onEscape)
    document.removeEventListener('keydown', onConfirmKey)
})
</script>

<template>
    <VDialog
        v-model="isVisible"
        scrollable
        persistent
        :max-width="maxWidth"
    >
        <VCard :title="header">
            <!-- 👉 dialog close btn -->
            <DialogCloseBtn
                variant="text"
                size="default"
                @click="handleCancel"
            />
            <VDivider />
            <VCardText class="mt-3">
                <div v-if="useHtml" v-html="text"></div>
                <div v-else class="text-content">{{ text }}</div>
            </VCardText>
            <VDivider />
            <VCardActions class="pa-4">
                <VSpacer />
                <VBtn
                    color="secondary"
                    variant="outlined"
                    @click="handleCancel"
                >
                    Cancel
                </VBtn>
                <VBtn
                    :color="confirmButtonColor"
                    variant="elevated"
                    @click="handleConfirm"
                >
                    {{ confirmButtonText }}
                </VBtn>
            </VCardActions>
        </VCard>
    </VDialog>
</template>

<style scoped>
.text-content {
    white-space: pre-line;
}
</style>
