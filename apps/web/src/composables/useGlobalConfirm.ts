// App-wide promise-based confirm dialog. GlobalConfirmDialog.vue renders the
// singleton state; call confirmDialog(...) from anywhere for a yes/no answer.
export interface GlobalConfirmOptions {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'danger' | 'warning' | 'info'
  details?: string[]
}

const state = reactive({
  open: false,
  title: '',
  message: '',
  confirmLabel: 'Confirm',
  cancelLabel: 'Cancel',
  tone: undefined as 'danger' | 'warning' | 'info' | undefined,
  details: [] as string[],
})

let resolver: ((result: boolean) => void) | null = null

export function useGlobalConfirm() {
  function confirmDialog(opts: GlobalConfirmOptions): Promise<boolean> {
    resolver?.(false)
    resolver = null
    state.title = opts.title
    state.message = opts.message
    state.confirmLabel = opts.confirmLabel ?? 'Confirm'
    state.cancelLabel = opts.cancelLabel ?? 'Cancel'
    state.tone = opts.tone ?? 'info'
    state.details = opts.details ?? []
    state.open = true

    return new Promise(resolve => {
      resolver = resolve
    })
  }

  function resolve(result: boolean) {
    resolver?.(result)
    resolver = null
    state.open = false
  }

  return { state, confirmDialog, resolve }
}
