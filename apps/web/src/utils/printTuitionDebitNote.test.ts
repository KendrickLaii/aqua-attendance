import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { buildDebitNotePrintHtml, debitNoteTeamCopy } from './printTuitionDebitNote'
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
    assert.match(html, /202611001\/26/)
    assert.match(html, /19\/8\/26/)
    assert.match(html, /公司章程/)
    assert.match(html, /4,000\.00/)
    assert.match(html, /1,500\.00/)
    assert.match(html, /5,500\.00/)
    assert.match(html, /<svg/)
    assert.match(html, /\/brands\/drj-letterhead\.png/)
    assert.match(html, /THANK YOU FOR YOUR BUSINESS/)
    assert.match(html, /\/brands\/drj-logo\.png/)
    assert.doesNotMatch(html, /BEASHKHH/)
    assert.match(html, /Add invoice_payment/)
    assert.doesNotMatch(html, /月份/)
  })

  it('prints the client address, code, and day-first date on a debit note', () => {
    const html = buildDebitNotePrintHtml(debitNote({
      invoiceNo: '2221',
      studentName: '每運宏 (ZA250204)',
      clientCode: 'ZA250204',
      billTo: '15/F, Tower 2',
      issueDate: new Date(2026, 10, 13),
    }))

    assert.match(html, /<div class="who">每運宏<\/div><div class="addr">15\/F, Tower\u00A02<\/div>/)
    assert.match(html, /ZA250204\/2221\/26/)
    assert.match(html, /13\/11\/26/)
  })

  it('wraps a bill-to address after commas and keeps each phrase together', () => {
    const html = buildDebitNotePrintHtml(debitNote({
      billTo: 'Hung To Road, Kwun Tong, Hong Kong',
    }))

    assert.match(html, /Hung\u00A0To\u00A0Road, Kwun\u00A0Tong, Hong\u00A0Kong/)
  })

  it('prints team payment text and leaves the block empty when it is missing', () => {
    const copy = debitNoteTeamCopy({
      details: {
        invoice_payment: 'Pay by FPS',
        invoice_footer: 'Thank you\nDRJ',
        floor: '15',
      },
    })

    assert.deepEqual(copy, { paymentText: 'Pay by FPS' })

    const html = buildDebitNotePrintHtml(debitNote({
      paymentText: copy.paymentText,
    }))

    assert.match(html, /Pay by FPS/)
    assert.match(html, /THANK YOU FOR YOUR BUSINESS/)
    assert.doesNotMatch(html, /Thank you<br>DRJ/)

    const empty = buildDebitNotePrintHtml(debitNote())

    assert.match(empty, /Add invoice_payment/)
  })

  it('uses a receipt heading and number when asked', () => {
    const html = buildDebitNotePrintHtml(debitNote({
      title: 'OFFICIAL RECEIPT',
      numberLabel: 'NO.',
      invoiceNo: 'R-18',
    }))

    assert.match(html, /OFFICIAL RECEIPT/)
    assert.match(html, /NO\./)
    assert.match(html, /R-18/)
    assert.doesNotMatch(html, /DN NO:/)
  })
})
