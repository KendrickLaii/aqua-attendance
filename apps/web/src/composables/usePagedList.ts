export function usePagedList(options?: {
  pageSize?: number
  pageSizeOptions?: number[]
}) {
  const page = ref(1)
  const pageSize = ref(options?.pageSize ?? 40)
  const pageSizeOptions = options?.pageSizeOptions ?? [10, 20, 40, 60, 100]
  const totalCount = ref(0)

  const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))

  function listCaption(itemCount: number, noun = 'record') {
    if (totalCount.value === 0)
      return ''

    const from = (page.value - 1) * pageSize.value + 1
    const to = from + itemCount - 1
    const plural = totalCount.value === 1 ? noun : `${noun}s`

    if (totalCount.value <= pageSize.value)
      return `${totalCount.value} ${plural}`

    return `${from}–${to} of ${totalCount.value}`
  }

  function resetPage() {
    page.value = 1
  }

  return {
    page,
    pageSize,
    pageSizeOptions,
    totalCount,
    totalPages,
    listCaption,
    resetPage,
  }
}
