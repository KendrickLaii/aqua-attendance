// Standard pending-confirmation state for AttendanceConfirmDialog.
// Usage: const confirm = useConfirmAction()
//   confirm.ask('Void DO-…', 'Voiding will return N items to stock.', { label: 'Void' }, async () => { ... })
//   <AttendanceConfirmDialog v-model="confirm.open" :title="confirm.title"
//     :confirm-label="confirm.label" :confirm-color="confirm.color" :loading="confirm.loading"
//     @confirm="confirm.run">{{ confirm.message }}</AttendanceConfirmDialog>
export function useConfirmAction() {
  const state = reactive({
    open: false,
    title: '',
    message: '',
    label: 'Confirm',
    color: 'error',
    loading: false,
  })

  let action: (() => Promise<void>) | null = null

  function ask(
    title: string,
    message: string,
    opts: { label?: string; color?: string },
    fn: () => Promise<void>,
  ) {
    state.title = title
    state.message = message
    state.label = opts.label ?? 'Confirm'
    state.color = opts.color ?? 'error'
    action = fn
    state.open = true
  }

  async function run() {
    state.loading = true
    try {
      await action?.()
      state.open = false
    }
    finally {
      state.loading = false
    }
  }

  return { ...toRefs(state), ask, run }
}
