import { $attendanceApi } from '@/utils/attendanceApi'

export async function getAutoCheckoutStatus(): Promise<{
  still_checked_in_count: number
  enabled?: boolean
}> {
  return await $attendanceApi('/auto-checkout/status')
}

export async function triggerAutoCheckout(options?: {
  targetDate?: string
  unitIds?: string[]
}): Promise<{
  target_date: string
  created_events: number
  message: string
  disabled?: boolean
}> {
  const body: Record<string, unknown> = {}
  if (options?.targetDate)
    body.target_date = options.targetDate
  if (options?.unitIds)
    body.unit_ids = options.unitIds

  return await $attendanceApi('/auto-checkout/run', { method: 'POST', body })
}
