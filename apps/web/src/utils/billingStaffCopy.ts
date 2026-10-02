/** Staff-facing Cantonese hints. Button labels stay English. */

export const JOIN_CLASS_HINT = '將學生加呢堂。之後去 Invoices 撳 Generate 先會出單。'

export const RENEW_SUBTITLE = '同一筆報名。發票只顯示月份，例如 Sept-26，唔會印開始同結束日。'

export const ONGOING_END_DATE_HINT = '留空就係 Ongoing。入班後可以撳 Set end 設最後計費日；過咗結束日會自動 Leave。'

export const ONGOING_SET_END_HINT = '撳 Set end 就可以設最後計費日。過咗呢日會自動 Leave。'

export const SET_END_HINT =
  '而家係 Ongoing，之後每個月 Generate 都會包呢個學生。下面個日期預設係今個月最後一日。呢日之後嘅月份唔會再出單。重疊到嘅月份仍然收成個月費。香港日期過咗結束日之後，開名冊會自動 Leave（變 Left）。'

export const RENEW_DATE_HINT = '儲存前可以改呢個日期。'

export const RENEW_END_REQUIRED = '請揀最後計費日。'

export const RENEW_END_BEFORE_START = '最後計費日唔可以早過開始日。'

export const RENEW_END_NOT_LATER = '新結束日一定要遲過而家嘅結束日。如果只想計完今個月，改個日期。'

export function renewExtendHint(start: string, end: string): string {
  return `而家計 ${start} 至 ${end}。下面個日期預設係下一個月最後一日，所以 9月10日 會變 10月31日，10月就可以出單。如果只想計到今個月，例如 9月30日，儲存前改個日期。每個月仍然係成個月費。`
}

export function renewSavedHint(name: string, end: string): string {
  return `${name} 已續到 ${end}。新月份要去 Invoices 撳 Generate 先出單。`
}

export function setEndSavedHint(name: string, end: string): string {
  return `${name} 計到 ${end} 為止。之後嘅月份唔會再 Generate。`
}

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
