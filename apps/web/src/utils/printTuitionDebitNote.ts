import { invoiceCurrencySymbol } from '@/utils/invoiceDisplay'
import type { TuitionInvoicePrintData, TuitionInvoicePrintLine } from '@/utils/printTuitionInvoice'

/** Round mark and the supplied letterhead artwork, inlined before print. */
export const DRJ_DEBIT_NOTE_LOGO = '/brands/drj-logo.png'

export const DRJ_DEBIT_NOTE_LETTERHEAD = '/brands/drj-letterhead.png'

export function debitNoteTeamCopy(location: {
  details?: Record<string, unknown> | null
}): { paymentText: string } {
  const details = location.details ?? {}

  const paymentText = typeof details.invoice_payment === 'string'
    ? details.invoice_payment.trim()
    : ''

  return { paymentText }
}

function textBlock(value: string): string {
  return escapeHtml(value).replace(/\n/g, '<br>')
}

/** Keep each comma-separated phrase together. Lines may break after a comma. */
function glueAddress(value: string): string {
  return value.split('\n').map(glueAddressLine).join('\n')
}

function glueAddressLine(line: string): string {
  const pieces = line.split(/([,，、])/)

  const glued = pieces.map((piece, index) => {
    if (index % 2 === 1)
      return `${piece} `

    return piece.trim().replace(/[ \t]+/g, '\u00A0')
  }).join('')

  return glued.trim()
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatMoney(value: number | null): string {
  if (value == null || Number.isNaN(value))
    return ''

  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/** Real lines print "-" for zero; blank filler rows (null) stay empty. */
function formatMoneyOrDash(value: number | null): string {
  if (value == null || Number.isNaN(value))
    return ''

  return Number(value) === 0 ? '-' : formatMoney(value)
}

function formatQtyOrDash(value: number | null): string {
  if (value == null || Number.isNaN(value))
    return ''

  return Number(value) === 0
    ? '-'
    : Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

function detailCells(line: TuitionInvoicePrintLine | null, detailed: boolean): string {
  if (!detailed)
    return ''

  return `
          <td class="num">${escapeHtml(formatMoneyOrDash(line?.fee ?? null))}</td>
          <td class="qty">${escapeHtml(formatQtyOrDash(line?.qty ?? null))}</td>`
}

/** Debit notes use D/M/YY, for example 13/11/26. */
function formatDebitDate(date: Date): string {
  if (Number.isNaN(date.getTime()))
    return ''

  const year = String(date.getFullYear()).slice(2)

  return `${date.getDate()}/${date.getMonth() + 1}/${year}`
}

function billToBlock(data: TuitionInvoicePrintData): string {
  let name = data.studentName.trim()

  const code = data.clientCode?.trim()

  if (code && name.endsWith(`(${code})`))
    name = name.slice(0, -(code.length + 2)).trim()

  const address = (data.billTo ?? '').trim()

  const who = name ? `<div class="who">${escapeHtml(name)}</div>` : ''

  const addr = address ? `<div class="addr">${escapeHtml(glueAddress(address))}</div>` : ''

  return `${who}${addr}`
}

function debitNoteNumber(data: TuitionInvoicePrintData): string {
  const year = Number.isNaN(data.issueDate.getTime())
    ? ''
    : String(data.issueDate.getFullYear()).slice(2)

  return [data.clientCode?.trim(), data.invoiceNo.trim(), year].filter(Boolean).join('/')
}

const EMPTY_PAYMENT_HINT = 'Add invoice_payment in this Team Extra Details.'

/** Blank rows keep a short bill the same height as the DRJ sample. */
const MIN_BODY_ROWS = 15

/**
 * DRJ debit note. Logo, letterhead, and footer are the fixed company images.
 * Payment text comes from the team JSON. An empty value prints a reminder.
 */
export function buildDebitNotePrintHtml(data: TuitionInvoicePrintData): string {
  const symbol = invoiceCurrencySymbol(data.currency)

  const rows = data.lines.filter(line => line.course.trim() || line.amount != null)

  const topRemark = data.topRemark?.trim() ?? ''

  while (rows.length + (topRemark ? 1 : 0) < MIN_BODY_ROWS)
    rows.push({ month: '', course: '', fee: null, qty: null, amount: null })

  const detailed = data.printVersion === 'detailed'

  const remarkRow = topRemark
    ? `        <tr>
          <td class="desc">${textBlock(topRemark)}</td>${detailCells(null, detailed)}
          <td class="amt"></td>
        </tr>
`
    : ''

  const bodyRows = remarkRow + rows
    .map(line => `        <tr>
          <td class="desc">${escapeHtml(line.course)}</td>${detailCells(line, detailed)}
          <td class="amt">${escapeHtml(formatMoneyOrDash(line.amount))}</td>
        </tr>`)
    .join('\n')

  const headRow = detailed
    ? `          <th>DESCRIPTION(S)</th>
          <th class="num">PRICE</th>
          <th class="qty">QTY</th>
          <th class="amt">AMOUNT (${escapeHtml(symbol)})</th>`
    : `          <th>DESCRIPTION(S)</th>
          <th>AMOUNT (${escapeHtml(symbol)})</th>`

  const total = data.lines.reduce((sum, line) => sum + (line.amount ?? 0), 0)

  const bottomRemark = data.remark?.trim()
    ? `<div class="remark bottom">${textBlock(data.remark.trim())}</div>`
    : ''

  const logoSrc = data.logoUrl || DRJ_DEBIT_NOTE_LOGO

  const letterheadSrc = data.letterheadUrl || DRJ_DEBIT_NOTE_LETTERHEAD

  const payment = data.paymentText?.trim()
    ? textBlock(data.paymentText.trim())
    : ''

  const year = Number.isNaN(data.issueDate.getTime())
    ? new Date().getFullYear()
    : data.issueDate.getFullYear()

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Debit note ${escapeHtml(data.invoiceNo)} — ${escapeHtml(data.studentName)}</title>
  <style>
    * { box-sizing: border-box; }
    @page { size: A4 portrait; margin: 0; }
    html, body {
      margin: 0;
      padding: 0;
      background: #fff;
      color: #1a1a1a;
    }
    body {
      font-family: Arial, "Microsoft JhengHei", "PingFang HK", sans-serif;
      font-size: 12px;
    }
    .sheet {
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 12mm 16mm 12mm;
      display: flex;
      flex-direction: column;
    }
    .brandbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8mm;
    }
    .logo {
      width: 18mm;
      height: 18mm;
      object-fit: contain;
      flex: 0 0 auto;
    }
    .wordmark {
      width: auto;
      height: 42mm;
      max-width: 78%;
      object-fit: contain;
      object-position: right top;
    }
    .meta {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-top: 8mm;
      gap: 12mm;
    }
    .billto {
      flex: 1 1 auto;
      min-width: 0;
      max-width: 95mm;
      padding-right: 8mm;
    }
    .billto .label {
      font-weight: 700;
      margin-bottom: 2px;
    }
    .billto .addr {
      max-width: 72mm;
      white-space: pre-wrap;
      overflow-wrap: break-word;
    }
    .refs {
      margin-left: auto;
      flex: 0 0 auto;
      white-space: nowrap;
    }
    .refs div { margin: 1px 0; }
    .refs .k {
      display: inline-block;
      width: 16mm;
      font-weight: 700;
    }
    h1 {
      text-align: center;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.06em;
      margin: 4mm 0 3mm;
    }
    table.items {
      width: 100%;
      border-collapse: collapse;
    }
    table.items th, table.items td {
      border: 1px solid #111;
    }
    table.items tbody td {
      border-top: none;
      border-bottom: none;
    }
    table.items tbody tr:last-child td {
      border-bottom: 1px solid #111;
    }
    table.items th {
      text-align: center;
      font-weight: 700;
      padding: 4px 8px;
    }
    table.items td.desc {
      padding: 0 8px;
      white-space: pre-wrap;
      text-align: left;
    }
    table.items td.amt {
      text-align: right;
    }
    table.items td.amt {
      width: ${detailed ? '22%' : '36%'};
      padding: 0 8px;
      white-space: nowrap;
    }
    table.items th.num, table.items td.num {
      width: 18%;
      padding: 0 8px;
      text-align: right;
      white-space: nowrap;
    }
    table.items th.qty, table.items td.qty {
      width: 10%;
      padding: 0 8px;
      text-align: right;
      white-space: nowrap;
    }
    table.items th.num, table.items th.qty, table.items th.amt {
      text-align: center;
    }
    .remark {
      line-height: 1.4;
      overflow-wrap: break-word;
    }
    .remark.bottom { margin: 2mm 0 0; }
    table.items tbody tr { height: 6.6mm; }
    table.items td { vertical-align: middle; }
    .after {
      display: grid;
      grid-template-columns: 1fr ${detailed ? '22%' : '36%'};
      align-items: start;
      margin-top: 4mm;
    }
    .total {
      width: 100%;
      border-collapse: collapse;
    }
    .total td {
      border: 1px solid #111;
      padding: 3px 8px;
      font-weight: 700;
      text-align: center;
    }
    .total td:first-child {
      border-right: none;
    }
    .total td.amt {
      border-left: none;
      text-align: right;
    }
    .pay {
      padding-top: 4mm;
      padding-right: 6mm;
      line-height: 1.45;
      font-size: 11px;
    }
    .pay.hint {
      color: #888;
      font-style: italic;
    }
    .foot {
      margin-top: auto;
      padding-top: 8mm;
    }
    .foot-svg {
      width: 100%;
      height: auto;
      display: block;
    }
    @media print {
      html, body, .sheet { width: 210mm; margin: 0; }
      .sheet { min-height: 297mm; }
    }
  </style>
</head>
<body>
  <div class="sheet">
    <header class="brandbar">
      <img class="logo" src="${escapeHtml(logoSrc)}" alt="" />
      <img class="wordmark" src="${escapeHtml(letterheadSrc)}" alt="DRJ INTERNATIONAL" />
    </header>

    <div class="meta">
      <div class="billto">
        <div class="label">BILL TO:</div>
        ${billToBlock(data)}
      </div>
      <div class="refs">
        <div><span class="k">DN NO:</span> ${escapeHtml(debitNoteNumber(data))}</div>
        <div><span class="k">DATE:</span> ${escapeHtml(formatDebitDate(data.issueDate))}</div>
      </div>
    </div>

    <h1>DEBIT NOTE</h1>

    <table class="items">
      <thead>
        <tr>
${headRow}
        </tr>
      </thead>
      <tbody>
${bodyRows}
      </tbody>
    </table>
    ${bottomRemark}

    <div class="after">
      <div>${payment
        ? `<div class="pay">${payment}</div>`
        : `<div class="pay hint">${EMPTY_PAYMENT_HINT}</div>`}</div>
      <table class="total">
        <tr>
          <td>Total ${escapeHtml(symbol)}</td>
          <td class="amt">${escapeHtml(formatMoneyOrDash(total))}</td>
        </tr>
      </table>
    </div>

    <div class="foot">
    <svg class="foot-svg" viewBox="0 0 760 28" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Thank you for your business">
      <line x1="0" y1="2" x2="760" y2="2" stroke="#d5d5d5" stroke-width="1" />
      <text x="0" y="22" fill="#9a9a9a" font-family="Arial, Helvetica, sans-serif" font-size="11" letter-spacing="0.4">THANK YOU FOR YOUR BUSINESS</text>
      <text x="760" y="22" text-anchor="end" fill="#9a9a9a" font-family="Arial, Helvetica, sans-serif" font-size="11">© ${year} For more information, contact DRJ</text>
    </svg>
    </div>
  </div>
</body>
</html>`
}
