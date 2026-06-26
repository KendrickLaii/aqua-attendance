import { $attendanceApi } from '@/utils/attendanceApi'

export async function getAutoCheckoutStatus(): Promise<{ still_checked_in_count: number }> {
  return await $attendanceApi('/auto-checkout/status')
}

export async function triggerAutoCheckout(options?: {
  targetDate?: string
  productIds?: string[]
}): Promise<{ target_date: string; created_events: number; message: string }> {
  const body: Record<string, unknown> = {}
  if (options?.targetDate)
    body.target_date = options.targetDate
  if (options?.productIds)
    body.product_ids = options.productIds

  return await $attendanceApi('/auto-checkout/run', { method: 'POST', body })
}
