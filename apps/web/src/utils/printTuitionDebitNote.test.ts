import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { buildDebitNotePrintHtml } from './printTuitionDebitNote'
import type { TuitionInvoicePrintData } from './printTuitionInvoice'

function debitNote(over: Partial<TuitionInvoicePrintData> = {}): TuitionInvoicePrintData {
  return {
    invoiceNo: '202611001',
    issueDate: new Date(2026, 7, 19),
    studentName: '每運宏',
    lines: [
      { month: '', course: '公司章程', fee: 4000, qty: 1, amount: 4000 },
      { month: '', course: '公司印章', fee: 1500, qty: 1, amount: 1500 },
    ],
    template: 'debit-note',
    ...over,
  }
}

describe('printTuitionDebitNote', () => {
  it('prints bill-to, DN number, date, lines, and total on the DRJ debit note', () => {
    const html = buildDebitNotePrintHtml(debitNote())

    assert.match(html, /DEBIT NOTE/)
    assert.match(html, /BILL TO:/)
    assert.match(html, /每運宏/)
    assert.match(html, /DN NO:/)
    assert.match(html, /202611001/)
    assert.match(html, /8\/19\/26/)
    assert.match(html, /公司章程/)
    assert.match(html, /4,000\.00/)
    assert.match(html, /1,500\.00/)
    assert.match(html, /5,500\.00/)
    assert.match(html, /DRJ INTERNATIONAL/)
    assert.match(html, /BEASHKHH/)
    assert.doesNotMatch(html, /月份/)
  })
})
