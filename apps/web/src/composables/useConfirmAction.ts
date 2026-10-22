// Standard pending-confirmation state for AttendanceConfirmDialog.
// Usage: const confirm = useConfirmAction()
//   confirm.ask('Void DO-…', '庫存會加回去', { label: 'Void', tone: 'danger', details: [...] }, async () => { ... })
//   <AttendanceConfirmDialog v-model="confirm.open" :title="confirm.title"
//     :confirm-label="confirm.label" :tone="confirm.tone" :details="confirm.details"
//     :confirm-color="confirm.color" :loading="confirm.loading"
//     @confirm="confirm.run">{{ confirm.message }}</AttendanceConfirmDialog>
export function useConfirmAction() {
  const state = reactive({
    open: false,
    title: '',
    message: '',
    label: 'Confirm',
    color: 'error',
    tone: undefined as 'danger' | 'warning' | 'info' | undefined,
    details: [] as string[],
    loading: false,
  })

  let action: (() => Promise<void>) | null = null

  function ask(
    title: string,
    message: string,
    opts: { label?: string, color?: string, tone?: 'danger' | 'warning' | 'info', details?: string[] },
    fn: () => Promise<void>,
  ) {
    state.title = title
    state.message = message
    state.label = opts.label ?? 'Confirm'
    state.color = opts.color ?? 'error'
    state.tone = opts.tone
    state.details = opts.details ?? []
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
