import type { TuitionInvoice } from '@/api/attendance/tuitionInvoices'

// Hosted logo shown top-left on the printed invoice (same pattern as
// location photo URLs). Paste the image URL here; leave empty to hide it.
const INVOICE_LOGO_URL = ''

export interface TuitionInvoicePrintLine {
  month: string
  course: string
  fee: number | null
  qty: number | null
  amount: number | null
}

export interface TuitionInvoicePrintHeader {
  nameEn: string
  nameZh: string
  regNo: string
  address: string
  phone: string
}

export interface TuitionInvoicePrintData {
  invoiceNo: string
  issueDate: Date
  studentName: string
  lines: TuitionInvoicePrintLine[]
  logoUrl?: string
  header?: TuitionInvoicePrintHeader
}

const DEFAULT_HEADER: TuitionInvoicePrintHeader = {
  nameEn: 'YING TAT EDUCATION CENTRE',
  nameZh: '盈達教育中心',
  regNo: '613118',
  address: '華富(二)邨商場5樓1-2號舖',
  phone: '2237-1299',
}

const MIN_ROWS = 5

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec']

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

function formatInvoiceDate(date: Date): string {
  if (Number.isNaN(date.getTime()))
    return ''

  return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`
}

/** "2026-09-01" -> "Sept-26" */
export function invoiceMonthLabel(periodStart: string): string {
  const date = new Date(`${periodStart}T00:00:00`)
  if (Number.isNaN(date.getTime()))
    return periodStart

  return `${MONTH_LABELS[date.getMonth()]}-${String(date.getFullYear()).slice(2)}`
}

export function tuitionInvoicePrintData(
  invoice: TuitionInvoice,
  options?: { logoUrl?: string; header?: TuitionInvoicePrintHeader },
): TuitionInvoicePrintData {
  const studentName = invoice.unit_name
    ? `${invoice.unit_name}${invoice.unit_code ? ` (${invoice.unit_code})` : ''}`
    : (invoice.unit_code ?? '')

  return {
    invoiceNo: invoice.invoice_no ?? '',
    issueDate: invoice.issued_at ? new Date(invoice.issued_at) : new Date(),
    studentName,
    logoUrl: options?.logoUrl,
    header: options?.header,
    lines: invoice.lines.map(line => ({
      month: invoiceMonthLabel(invoice.period_start),
      course: line.name_zh || line.sku_code,
      fee: Number(line.unit_price),
      qty: Number(line.quantity),
      amount: Number(line.amount),
    })),
  }
}

/** Call synchronously from a click handler before any await. */
export function openTuitionInvoicePrintPlaceholder(): Window {
  const printWindow = window.open('about:blank', '_blank')
  if (!printWindow)
    throw new Error('Pop-up blocked. Allow pop-ups to print the invoice.')

  printWindow.document.open()
  printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Invoice</title></head>
<body style="font-family:PMingLiU,'Microsoft JhengHei',serif;padding:24px;color:#333">
  <p>Preparing invoice…</p>
</body></html>`)
  printWindow.document.close()

  return printWindow
}

export function renderTuitionInvoicePrintWindow(printWindow: Window, data: TuitionInvoicePrintData) {
  const rows = [...data.lines]
  while (rows.length < MIN_ROWS)
    rows.push({ month: '', course: '', fee: null, qty: null, amount: null })

  const total = data.lines.reduce((sum, line) => sum + (line.amount ?? 0), 0)

  const lineRows = rows.map(line => `      <tr>
        <td>${escapeHtml(line.month)}</td>
        <td>${escapeHtml(line.course)}</td>
        <td class="num">${escapeHtml(formatMoney(line.fee))}</td>
        <td class="num">${escapeHtml(formatMoney(line.qty))}</td>
        <td class="num">${escapeHtml(formatMoney(line.amount))}</td>
      </tr>`).join('\n')

  const logoUrl = data.logoUrl || INVOICE_LOGO_URL

  const logoCell = logoUrl
    ? `<div class="cell logo-cell"><img src="${escapeHtml(logoUrl)}" alt="logo" /></div>`
    : ''

  const header = data.header ?? DEFAULT_HEADER

  const centreLines = [
    header.regNo ? `<div class="reg">學校註冊編號: ${escapeHtml(header.regNo)}</div>` : '',
    header.address ? `<div>地址: ${escapeHtml(header.address)}</div>` : '',
    header.phone ? `<div>電話: ${escapeHtml(header.phone)}</div>` : '',
  ].filter(Boolean).join('\n      ')

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Invoice ${escapeHtml(data.invoiceNo)} — ${escapeHtml(data.studentName)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: "DFKai-SB", "標楷體", KaiTi, "Microsoft JhengHei", "PMingLiU", serif;
      margin: 0;
      padding: 24px 32px;
      color: #000;
      font-size: 15px;
    }
    .header {
      display: table;
      width: 100%;
    }
    .header > .cell {
      display: table-cell;
      vertical-align: top;
    }
    .logo-cell {
      width: 120px;
      padding-right: 12px;
    }
    .logo-cell img {
      max-width: 110px;
      max-height: 110px;
    }
    .centre {
      line-height: 1.45;
    }
    .centre .name-en {
      font-family: Arial, "Microsoft JhengHei", sans-serif;
      font-size: 19px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .centre .name-zh {
      font-size: 17px;
      font-weight: 700;
    }
    .centre .reg {
      font-size: 12px;
    }
    .title-cell {
      font-family: Arial, "Microsoft JhengHei", sans-serif;
      font-size: 30px;
      font-weight: 700;
      text-align: right;
      white-space: nowrap;
      width: 1%;
    }
    .idrow {
      width: 100%;
      margin-top: 6px;
      line-height: 1.9;
    }
    .idrow .right {
      float: right;
      text-align: left;
    }
    .idrow .label {
      display: inline-block;
      min-width: 4.5em;
    }
    .fill {
      display: inline-block;
      min-width: 11em;
      border-bottom: 1px solid #000;
      text-align: right;
      padding: 0 4px;
    }
    .fill.wide {
      min-width: 16em;
      text-align: left;
    }
    .student {
      clear: both;
      margin-top: 4px;
      line-height: 1.9;
    }
    table.items {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 15px;
    }
    table.items th, table.items td {
      border: 1px solid #000;
      padding: 4px 8px;
      height: 26px;
    }
    table.items th {
      font-weight: 700;
      text-align: left;
    }
    table.items th.num, table.items td.num {
      text-align: right;
      white-space: nowrap;
    }
    .col-month { width: 16%; }
    .col-course { width: 36%; }
    .col-fee { width: 15%; }
    .col-qty { width: 13%; }
    .col-amount { width: 20%; }
    .total-row {
      width: 100%;
      margin-top: 0;
    }
    .total-row .amount {
      float: right;
      width: 20%;
      border: 1px solid #000;
      border-top: none;
      text-align: right;
      padding: 4px 8px;
      font-weight: 700;
    }
    .foot {
      clear: both;
      display: table;
      width: 100%;
      margin-top: 28px;
    }
    .foot > .cell {
      display: table-cell;
      vertical-align: top;
    }
    .payinfo {
      line-height: 1.7;
      width: 70%;
    }
    .issuedby {
      width: 30%;
    }
    .issuedby .box {
      border: 1px solid #000;
      height: 90px;
      margin-top: 4px;
    }
    .note {
      margin-top: 16px;
      font-size: 12.5px;
      line-height: 1.6;
    }
    .tear {
      margin-top: 22px;
      border-bottom: 2px dotted #000;
    }
    @media print {
      body { padding: 10mm 14mm; }
    }
  </style>
</head>
<body>
  <div class="header">
    ${logoCell}
    <div class="cell centre">
      <div class="name-en">${escapeHtml(header.nameEn)}</div>
      <div class="name-zh">${escapeHtml(header.nameZh)}</div>
      ${centreLines}
    </div>
    <div class="cell title-cell">INVOICE</div>
  </div>

  <div class="idrow">
    <div class="right"><span class="label">編號:</span><span class="fill">${escapeHtml(data.invoiceNo)}</span></div>
  </div>
  <div class="student">
    <div class="right" style="float:right"><span class="label">日期:</span><span class="fill">${escapeHtml(formatInvoiceDate(data.issueDate))}</span></div>
    <span class="label">學生姓名:</span><span class="fill wide">${escapeHtml(data.studentName)}</span>
  </div>

  <table class="items">
    <colgroup>
      <col class="col-month">
      <col class="col-course">
      <col class="col-fee">
      <col class="col-qty">
      <col class="col-amount">
    </colgroup>
    <thead>
      <tr>
        <th>月份</th>
        <th>課程</th>
        <th class="num">堂費</th>
        <th class="num">堂數</th>
        <th class="num">總額</th>
      </tr>
    </thead>
    <tbody>
${lineRows}
    </tbody>
  </table>
  <div class="total-row">
    <div class="amount">${escapeHtml(formatMoney(total))}</div>
  </div>

  <div class="foot">
    <div class="cell payinfo">
      費用可以現金或支票支付 或存入Wealth Impact Enterprise Limited<br>
      匯豐銀行(#004)戶口 #801-784430-838 或 轉數快 #114782808
    </div>
    <div class="cell issuedby">
      Issued by:
      <div class="box"></div>
    </div>
  </div>

  <div class="note">
    註: 上述費用是按照《教育(豁免)(提供非正規課程的私立學校)令》所訂明的條件收取。<br>
    &nbsp;&nbsp;&nbsp;&nbsp;所收取的費用是按每月等額計算。如學校未能按預訂安排開辦課程，<br>
    &nbsp;&nbsp;&nbsp;&nbsp;便會按照課程單張所載的退款政策及程序，向上述學生退回全部或部分費用。
  </div>
  <div class="tear"></div>
</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
}

export function printTuitionInvoice(printWindow: Window, data: TuitionInvoicePrintData) {
  renderTuitionInvoicePrintWindow(printWindow, data)
  printWindow.focus()
  printWindow.print()
}
