import { $attendanceApi } from '@/utils/attendanceApi'

export interface InvoiceJobOption {
  id: string
  location_id: string
  name: string
  created_at: string
}

export function listInvoiceJobs(locationId: string) {
  return $attendanceApi<InvoiceJobOption[]>('/invoice-jobs', { params: { location_id: locationId } })
}

export function createInvoiceJob(name: string, locationId: string) {
  return $attendanceApi<InvoiceJobOption>('/invoice-jobs', {
    method: 'POST',
    body: { name, location_id: locationId },
  })
}

export function deleteInvoiceJob(id: string) {
  return $attendanceApi<void>(`/invoice-jobs/${id}`, { method: 'DELETE' })
}
