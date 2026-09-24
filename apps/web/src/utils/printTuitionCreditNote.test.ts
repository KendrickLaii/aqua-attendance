import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { buildTuitionCreditNotePrintHtml } from './printTuitionCreditNote'
import type { TuitionInvoicePrintData } from './printTuitionInvoice'

function creditPrintData(over: Partial<TuitionInvoicePrintData> = {}): TuitionInvoicePrintData {
  return {
    invoiceNo: 'R01006RF',
    issueDate: new Date('2025-01-13T00:00:00'),
    studentName: '李 (ZA2409010)',
    lines: [{
      month: 'Jan-25',
      course: '功課輔導班',
      fee: -1785,
      qty: 17,
      amount: -1785,
    }],
    payableTo: 'TANG WING YIN',
    payeeName: 'TANG WING YIN',
    ...over,
  }
}

describe('printTuitionCreditNote', () => {
  it('prints refund request and acknowledgement with typed names and blank staff lines', () => {
    const html = buildTuitionCreditNotePrintHtml(creditPrintData())

    assert.match(html, /REFUND REQUEST/)
    assert.match(html, /REFUND ACKNOWLEDGEMENT/)
    assert.match(html, /CHEQUE PAYABLE TO/)
    assert.match(html, /TANG WING YIN/)
    assert.match(html, /PAID BY/)
    assert.match(html, /SUPERVISOR/)
    assert.match(html, /Issued by:/)
    assert.match(html, /Signature:/)
    assert.doesNotMatch(html, />X</)
    assert.equal((html.match(/class="sign-box"/g) ?? []).length, 2)
    assert.doesNotMatch(html, /PAID BY:<\/span><span class="fill">[^<]+/)
    assert.doesNotMatch(html, /SUPERVISOR:<\/span><span class="fill">[^<]+/)
  })
})
