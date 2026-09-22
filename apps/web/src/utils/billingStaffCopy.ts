/** Staff-facing Cantonese hints. Button labels stay English. */

export const JOIN_CLASS_HINT = '將學生加呢堂。之後去 Invoices 撳 Generate 先會出單。'

export const JOIN_FIRST_STUDENT = 'Join the first student with the form above.'

export const LEAVE_CLASS_CONFIRM =
  '呢個學生唔再讀呢堂。名會留低，之後可以 Back in class。已經出咗嘅單唔會改。想今個月唔出單：去 Invoices 再撳 Generate。'

export const REMOVE_RECORD_CONFIRM = '會刪走成條紀錄。學生只係唔讀，請用 Leave class。'

export const REMOVE_RECORD_BILLED = '呢個學生已經有帳單。請用 Leave class，唔好刪。'

export const INVOICE_CANCEL_GENERATED =
  '學生仲讀嘅話，再 Generate 會出返張單。想唔出：去 Courses 撳 Leave class，再返嚟 Generate。'

export const GENERATE_CONFIRM =
  '會換草稿單。已出／已收錢嘅單唔郁。如果學生仲讀，取消咗嘅單可能會出返嚟。'

export const BILLING_HELP_FIX = '改數：去 Courses 撳 Edit，再返 Invoices 撳 Generate。'

export const BILLING_HELP_STOP = '唔出單：去 Courses 撳 Leave class，再 Generate。'

export const BILLING_HELP_DONT_ONLY_CANCEL = '唔好淨係 Cancel 張單。'

export const MANUAL_CREDIT_HINT =
  '未收錢可以改張單。收咗錢就唔改舊單；打負數就當退錢（credit note）。'

export const VOID_RECEIPT_HINT =
  '作廢呢張收條。帳單會變返未收錢。編號暫時唔再用；想用返舊號，請再 Remove 呢張作廢收條。'

export const REMOVE_CANCELLED_INVOICE = '刪走呢張作廢單。編號之後可以再用。'

export const REMOVE_VOIDED_RECEIPT = '刪走呢張作廢收條。編號之後可以再用。'

export function leaveClassUnbilledNote(unbilledQty: number): string {
  if (unbilledQty <= 0)
    return ''

  return ` 仲有 ${unbilledQty} 堂未出單，可以用 Manual invoice 出。`
}

export function mapEnrollmentApiError(message: string): string {
  const lower = message.toLowerCase()
  if (lower.includes('billed') && (lower.includes('unenroll') || lower.includes('delet')))
    return REMOVE_RECORD_BILLED

  return message
}
