import type { PayrollRecord } from '@/api/attendance/payroll'
import {
  formatPayrollCurrency,
  formatPayrollDashAmount,
  safePayrollNumber,
} from '@/utils/payrollDisplay'

const COMPANY_NAME = 'WEALTH IMPACT ENTERPRISE LIMITED'

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatSlipDate(iso?: string | null) {
  const date = iso ? new Date(iso) : new Date()
  if (Number.isNaN(date.getTime()))
    return new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })

  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

function formatPeriodLabel(isoDate: string) {
  const date = new Date(`${isoDate}T00:00:00`)
  if (Number.isNaN(date.getTime()))
    return isoDate

  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

/** Call synchronously from a click handler before any await. */
export function openPayrollSlipPrintPlaceholder(): Window {
  const printWindow = window.open('about:blank', '_blank')
  if (!printWindow)
    throw new Error('Pop-up blocked. Allow pop-ups to print the payroll slip.')

  printWindow.document.open()
  printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Payroll Slip</title></head>
<body style="font-family:Times New Roman,Times,serif;padding:24px;color:#333">
  <p>Preparing payroll slip…</p>
</body></html>`)
  printWindow.document.close()

  return printWindow
}

export function renderPayrollSlipPrintWindow(printWindow: Window, record: PayrollRecord) {
  const name = record.unit_name || record.unit_code || record.unit_id
  const periodLabel = formatPeriodLabel(record.payroll_period_start)
  const slipDate = formatSlipDate(record.payment_date)
  const salary = safePayrollNumber(record.gross_pay)
  const adjustment2 = safePayrollNumber(record.adjustment_2)
  const adjustment2Label = (record.adjustment_2_remark || '').trim() || 'Adjustment 2'
  const adjustment2Amount = adjustment2 < 0
    ? `(${formatPayrollCurrency(Math.abs(adjustment2))})`
    : formatPayrollCurrency(adjustment2)
  const subtotal = safePayrollNumber(record.net_pay)
  const chequeNumber = (record.cheque_number || '').trim()
  const chequeAmount = safePayrollNumber(record.cheque_amount)
  const cashAmount = safePayrollNumber(record.cash_amount)

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Payroll Slip — ${escapeHtml(name)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: "Times New Roman", Times, serif;
      margin: 0;
      padding: 36px 48px;
      color: #111;
    }
    .company {
      text-align: center;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.04em;
      margin: 0 0 10px;
    }
    .title {
      text-align: center;
      font-size: 20px;
      font-weight: 700;
      text-decoration: underline;
      margin: 0 0 28px;
    }
    .meta {
      margin: 0 0 18px;
      font-size: 14px;
      line-height: 1.7;
    }
    .meta .label {
      display: inline-block;
      min-width: 9.5em;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 14px;
    }
    th, td {
      padding: 6px 4px;
      vertical-align: bottom;
    }
    th {
      border-bottom: 1px solid #111;
      font-weight: 700;
      text-align: left;
    }
    .pay-col {
      width: 11.5em;
    }
    th.amt, td.amt {
      text-align: right;
      white-space: nowrap;
      width: 22%;
    }
    .indent { padding-left: 1.5em; }
    .subtotal td.amt {
      border-bottom: 1px solid #111;
    }
    .split-cell {
      text-align: left;
      white-space: nowrap;
    }
    .split-label {
      display: inline-block;
      width: 4.6em;
    }
    .split-blank {
      display: inline-block;
      min-width: 5.5em;
      border-bottom: 1px solid #111;
      padding: 0 2px;
    }
    .cash-amt {
      border-bottom: 1px solid #111;
    }
    .grand td.amt {
      border-bottom: 3px double #111;
      font-weight: 700;
      padding-top: 8px;
    }
    .signoff {
      width: 100%;
      border-collapse: collapse;
      margin-top: 56px;
      font-size: 14px;
    }
    .signoff td {
      padding: 0;
      vertical-align: bottom;
    }
    .signoff tr + tr td {
      padding-top: 22px;
    }
    .sign-label {
      white-space: nowrap;
      width: 1%;
      padding-right: 10px !important;
    }
    .sign-blank {
      border-bottom: 1px solid #111;
      height: 1.5em;
      width: 38%;
      padding: 0 6px !important;
    }
    .sign-gap {
      width: 8%;
    }
    @media print {
      body { padding: 12mm 16mm; }
    }
  </style>
</head>
<body>
  <p class="company">${escapeHtml(COMPANY_NAME)}</p>
  <h1 class="title">PAYROLL SLIP</h1>
  <div class="meta">
    <div><span class="label">Date</span>: ${escapeHtml(slipDate)}</div>
    <div><span class="label">Name</span>: ${escapeHtml(name)}</div>
    <div><span class="label">Payroll period</span>: ${escapeHtml(periodLabel)}</div>
  </div>
  <table>
    <col>
    <col class="pay-col">
    <col class="amt">
    <thead>
      <tr>
        <th colspan="2">Description</th>
        <th class="amt">Amount (HK$)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td colspan="2">Salary for ${escapeHtml(periodLabel)}</td>
        <td class="amt">${escapeHtml(formatPayrollCurrency(salary))}</td>
      </tr>
      <tr>
        <td colspan="2" class="indent">${escapeHtml(adjustment2Label)}</td>
        <td class="amt">${escapeHtml(adjustment2Amount)}</td>
      </tr>
      <tr class="subtotal">
        <td colspan="2"></td>
        <td class="amt">${escapeHtml(formatPayrollCurrency(subtotal))}</td>
      </tr>
      <tr>
        <td></td>
        <td class="split-cell">
          <span class="split-label">Cheque#</span><span class="split-blank">${escapeHtml(chequeNumber)}</span>
        </td>
        <td class="amt">${escapeHtml(formatPayrollDashAmount(chequeAmount))}</td>
      </tr>
      <tr>
        <td></td>
        <td class="split-cell">
          <span class="split-label">Cash</span>
        </td>
        <td class="amt cash-amt">${escapeHtml(formatPayrollDashAmount(cashAmount))}</td>
      </tr>
      <tr class="grand">
        <td colspan="2"></td>
        <td class="amt">${escapeHtml(formatPayrollCurrency(subtotal))}</td>
      </tr>
    </tbody>
  </table>
  <table class="signoff">
    <tr>
      <td class="sign-label">Approved by :</td>
      <td class="sign-blank"></td>
      <td class="sign-gap"></td>
      <td class="sign-label">Received by :</td>
      <td class="sign-blank"></td>
    </tr>
    <tr>
      <td class="sign-label">Date :</td>
      <td class="sign-blank"></td>
      <td class="sign-gap"></td>
      <td class="sign-label">Date :</td>
      <td class="sign-blank"></td>
    </tr>
  </table>
</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
}

export function printPayrollSlip(printWindow: Window, record: PayrollRecord) {
  renderPayrollSlipPrintWindow(printWindow, record)
  printWindow.focus()
  printWindow.print()
}
