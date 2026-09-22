import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import type { TuitionInvoice, TuitionInvoiceLine } from '../api/attendance/tuitionInvoices'
import {
  billingLabel,
  classPreview,
  creditLinesFromInvoice,
  filterTuitionInvoices,
  formatInvoiceMoney,
  formatInvoiceQty,
  invoiceLineFormula,
  invoiceLinesEditable,
  invoiceOpenedBy,
  invoicePeriodLabel,
  invoiceStudentLabel,
  isCreditInvoice,
} from './invoiceDisplay'

function line(over: Partial<TuitionInvoiceLine> = {}): TuitionInvoiceLine {
  return {
    id: 'line-1',
    invoice_id: 'inv-1',
    enrollment_id: null,
    sku_id: null,
    sku_code: 'MATH-P3',
    name_zh: '小三数学',
    billing_unit: 'monthly',
    unit_price: 800,
    quantity: 1,
    amount: 800,
    month_label: 'Sept-26',
    staff_name: 'Ada',
    created_at: '',
    ...over,
  }
}

function invoice(over: Partial<TuitionInvoice> = {}): TuitionInvoice {
  return {
    id: 'inv-1',
    unit_id: 'u-1',
    unit_name: 'Chan Tai Man',
    unit_code: 'S001',
    manual_student_name: null,
    staff_name: 'Ada',
    location_id: 'loc-1',
    period_start: '2026-09-01',
    period_end: '2026-09-30',
    status: 'draft',
    kind: 'tuition',
    total: 800,
    notes: 'remark',
    invoice_no: 'INV-1',
    receipt_no: null,
    issued_at: null,
    lines: [line()],
    created_at: '',
    updated_at: '',
    ...over,
  }
}

describe('invoiceDisplay', () => {
  it('formats Hong Kong dollar amounts', () => {
    assert.equal(formatInvoiceMoney(800), 'HK$800.00')
    assert.equal(formatInvoiceMoney(-200), '-HK$200.00')
  })

  it('treats negative totals as credit notes and unpaid bills as editable', () => {
    assert.equal(isCreditInvoice(invoice({ total: -200 })), true)
    assert.equal(isCreditInvoice(invoice({ total: 800 })), false)
    assert.equal(invoiceLinesEditable('draft'), true)
    assert.equal(invoiceLinesEditable('issued'), true)
    assert.equal(invoiceLinesEditable('paid'), false)
    assert.equal(invoiceLinesEditable('void'), false)
  })

  it('builds credit-note lines with the opposite fee', () => {
    assert.deepEqual(creditLinesFromInvoice(invoice({
      lines: [line({ month_label: 'Sept-26', name_zh: '私補', unit_price: 200, quantity: 1 })],
    })), [{ month: 'Sept-26', course: '私補', fee: -200, qty: 1 }])
  })

  it('labels billing units in staff English', () => {
    assert.equal(billingLabel('per_session'), 'Per class')
    assert.equal(billingLabel('manual'), 'Manual')
    assert.equal(billingLabel('monthly'), 'Monthly')
  })

  it('formats line quantities by billing unit', () => {
    assert.equal(formatInvoiceQty(line({ billing_unit: 'per_session', quantity: 1 })), '1 session')
    assert.equal(formatInvoiceQty(line({ billing_unit: 'per_session', quantity: 8 })), '8 sessions')
    assert.equal(formatInvoiceQty(line({ billing_unit: 'manual', quantity: 1 })), '1')
    assert.equal(formatInvoiceQty(line({ billing_unit: 'monthly', quantity: 1 })), '1 month')
    assert.equal(formatInvoiceQty(line({ billing_unit: 'monthly', quantity: 2 })), '2 months')
  })

  it('shows qty × price for a line formula', () => {
    assert.equal(invoiceLineFormula(line()), '1 month × HK$800.00')
  })

  it('previews one or more class names', () => {
    assert.equal(classPreview(invoice({ lines: [] })), 'No lines')
    assert.equal(classPreview(invoice()), '小三数学')
    assert.equal(classPreview(invoice({
      lines: [line(), line({ id: 'line-2', name_zh: '英文' })],
    })), '小三数学 +1')
  })

  it('labels the billed period and who opened the bill', () => {
    assert.equal(invoicePeriodLabel(invoice()), '2026-09-01 – 2026-09-30')
    assert.equal(invoicePeriodLabel(invoice({ period_end: '2026-09-01' })), '2026-09-01')
    assert.equal(invoiceOpenedBy(invoice()), 'Ada')
    assert.equal(invoiceOpenedBy(invoice({ staff_name: '  ' })), '')
  })

  it('prefers enrolled student name, then walk-in name', () => {
    assert.equal(invoiceStudentLabel(invoice()), 'Chan Tai Man')
    assert.equal(invoiceStudentLabel(invoice({ unit_name: null, manual_student_name: 'Walk-in' })), 'Walk-in')
    assert.equal(invoiceStudentLabel(invoice({ unit_name: null, manual_student_name: null })), '—')
  })

  it('filters invoices by status and student / class / invoice no.', () => {
    const rows = [
      invoice(),
      invoice({
        id: 'inv-2',
        status: 'issued',
        unit_name: 'Wong Mei',
        invoice_no: 'INV-2',
        lines: [line({ name_zh: '英文', sku_code: 'ENG' })],
      }),
    ]

    assert.equal(filterTuitionInvoices(rows, { status: 'issued', query: '' }).length, 1)
    assert.equal(filterTuitionInvoices(rows, { status: 'all', query: 'wong' })[0].id, 'inv-2')
    assert.equal(filterTuitionInvoices(rows, { status: 'all', query: 'INV-1' })[0].id, 'inv-1')
    assert.equal(filterTuitionInvoices(rows, { status: 'all', query: '英文' })[0].id, 'inv-2')
    assert.equal(filterTuitionInvoices(rows, { status: 'paid', query: '' }).length, 0)
  })
})
