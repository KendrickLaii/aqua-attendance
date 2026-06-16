import { $attendanceApi } from '@/utils/attendanceApi'
import { fetchAttendanceListWithTotal, type AttendanceListResult } from '@/utils/attendanceListApi'

export interface Notification {
  id: string
  user_id: string | null
  product_id: string | null
  title: string
  message: string
  notification_type: string
  priority: string
  is_read: boolean
  read_at: string | null
  action_url: string | null
  extra_data: string | null
  created_at: string
  expires_at: string | null
}

export async function listNotifications(params?: {
  is_read?: boolean
  page?: number
  page_size?: number
}): Promise<Notification[]> {
  const result = await listNotificationsWithTotal(params)

  return result.items
}

export async function listNotificationsWithTotal(params?: {
  is_read?: boolean
  page?: number
  page_size?: number
}): Promise<AttendanceListResult<Notification>> {
  return await fetchAttendanceListWithTotal<Notification>('/notifications', params)
}

export async function markNotificationRead(notificationId: string): Promise<Notification> {
  return await $attendanceApi(`/notifications/${notificationId}`, {
    method: 'PATCH',
    body: { is_read: true },
  })
}

export async function markNotificationUnread(notificationId: string): Promise<Notification> {
  return await $attendanceApi(`/notifications/${notificationId}`, {
    method: 'PATCH',
    body: { is_read: false },
  })
}
