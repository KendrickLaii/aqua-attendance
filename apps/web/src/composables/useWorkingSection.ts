import type { FormData } from '@/components/dialogs/tax/WorkingSectionDialog.vue'

interface BasicInfoRef {
  validate: () => Promise<{ valid: boolean; errors: string[] }>
}

// Module-level singleton so alert state is shared across pages
const showAlert = ref(false)
const alertMessage = ref('')

export const useWorkingSection = () => {
  const router = useRouter()

  // Navigate to create page using the uuid selected by user
  const navigateToCreate = async (
    payload: FormData,
    onSuccess?: () => void,
  ) => {
    if (!payload.uuid) {
      alertMessage.value = 'No company selected'
      showAlert.value = true
      return
    }
    onSuccess?.()
    // Prefetch route chunk before push so Suspense / lazy route gap is minimal (less “full page reload” feel)
    try {
      await import('@/pages/tax/working-section/create/[uuid].vue')
    }
    catch {
      // still navigate; router will load the chunk again
    }
    await router.push({
      path: `/tax/working-section/create/${payload.uuid}`,
      query: { year: payload.year },
    })
  }

  /** Returns a handleNext handler bound to the given step and form ref. */
  const makeHandleNext = (
    currentStep: Ref<number>,
    basicInfoRef: Ref<BasicInfoRef | null>,
  ) => async (e: MouseEvent) => {
    if (currentStep.value === 0) {
      const { valid, errors } = await basicInfoRef.value?.validate() ?? { valid: true, errors: [] as string[] }
      if (!valid) {
        alertMessage.value = `Please fill in the following required fields:\n${errors.map(e => `• ${e}`).join('\n')}`
        showAlert.value = true
        return
      }
    }
    currentStep.value++
    ;(e.currentTarget as HTMLElement).blur()
  }

  return { showAlert, alertMessage, navigateToCreate, makeHandleNext }
}
