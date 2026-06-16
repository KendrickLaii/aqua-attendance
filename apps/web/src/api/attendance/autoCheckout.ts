import { $attendanceApi } from '@/utils/attendanceApi'

export async function getAutoCheckoutStatus(): Promise<{ still_checked_in_count: number }> {
  return await $attendanceApi('/auto-checkout/status')
}

export async function triggerAutoCheckout(targetDate?: string): Promise<{ target_date: string; created_events: number; message: string }> {
  const params = targetDate ? { target_date: targetDate } : undefined

  return await $attendanceApi('/auto-checkout/run', { method: 'POST', params })
}
