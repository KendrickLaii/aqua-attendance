import type { TuitionReceipt } from '@/api/attendance/tuitionReceipts'
import type { TuitionInvoicePrintHeader, TuitionInvoicePrintLine } from '@/utils/printTuitionInvoice'

const RECEIPT_LOGO_URL = ''

export interface TuitionReceiptPrintData {
  receiptNo: string
  receiptDate: Date
  studentName: string
  paidBy: string
  description: string
  lines: TuitionInvoicePrintLine[]
  logoUrl?: string
  header?: TuitionInvoicePrintHeader
  title?: string
}

const DEFAULT_HEADER: TuitionInvoicePrintHeader = {
  nameEn: 'YING TAT EDUCATION CENTRE',
  nameZh: '盈達教育中心',
  regNo: '613118',
  address: '華富(二)邨商場5樓1-2號舖',
  phone: '2237-1299',
}

const MIN_ROWS = 5

const COPIES = [
  { key: 'client', label: '' },
  { key: 'staff', label: '(ADMIN COPY)' },
] as const

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

function formatReceiptDate(date: Date): string {
  if (Number.isNaN(date.getTime()))
    return ''

  return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`
}

export function tuitionReceiptPrintData(
  receipt: TuitionReceipt,
  options?: { logoUrl?: string; header?: TuitionInvoicePrintHeader },
): TuitionReceiptPrintData {
  const studentName = receipt.payer_name || receipt.unit_name || ''

  return {
    receiptNo: receipt.receipt_no,
    receiptDate: new Date(`${receipt.receipt_date}T00:00:00`),
    studentName,
    paidBy: receipt.paid_by,
    description: receipt.description ?? '',
    logoUrl: options?.logoUrl,
    header: options?.header,
    title: Number(receipt.amount) < 0 ? 'CREDIT NOTE' : 'OFFICIAL RECEIPT',
    lines: receipt.print_lines.map(line => ({
      month: line.month,
      course: line.course,
      fee: Number(line.fee),
      qty: Number(line.qty),
      amount: Number(line.amount),
    })),
  }
}

/** Call synchronously from a click handler before any await. */
export function openTuitionReceiptPrintPlaceholder(): Window {
  const printWindow = window.open('about:blank', '_blank')
  if (!printWindow)
    throw new Error('Pop-up blocked. Allow pop-ups to print the receipt.')

  printWindow.document.open()
  printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Receipt</title></head>
<body style="font-family:PMingLiU,'Microsoft JhengHei',serif;padding:24px;color:#333">
  <p>Preparing receipt…</p>
</body></html>`)
  printWindow.document.close()

  return printWindow
}

function receiptCopyHtml(
  data: TuitionReceiptPrintData,
  copyLabel: string,
  lineRows: string,
  total: number,
  logoCell: string,
  centreLines: string,
  header: TuitionInvoicePrintHeader,
): string {
  return `  <article class="copy">
    <div class="copy-inner">
      <div class="header">
        ${logoCell}
        <div class="cell centre">
          <div class="name-en">${escapeHtml(header.nameEn)}</div>
          <div class="name-zh">${escapeHtml(header.nameZh)}</div>
          ${centreLines}
        </div>
        <div class="cell title-cell">
          <div class="title">${escapeHtml(data.title || 'OFFICIAL RECEIPT')}</div>
          ${copyLabel ? `<div class="copy-label">${escapeHtml(copyLabel)}</div>` : ''}
        </div>
      </div>

      <div class="idrow">
        <div class="right"><span class="label">編號:</span><span class="fill">${escapeHtml(data.receiptNo)}</span></div>
      </div>
      <div class="student">
        <div class="right" style="float:right"><span class="label">日期:</span><span class="fill">${escapeHtml(formatReceiptDate(data.receiptDate))}</span></div>
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
      <div class="remark"><span class="label">備註:</span>${escapeHtml(data.description)}</div>

      <div class="sign-row">
        <div class="sign-cell">
          <span class="sign-label">PAID BY:</span>
          <span class="sign-line">${escapeHtml(data.paidBy)}</span>
        </div>
        <div class="sign-cell issued">
          <span class="sign-label">Issued by:</span>
          <span class="sign-line"></span>
        </div>
      </div>
      <div class="sign-row supervisor-row">
        <div class="sign-cell">
          <span class="sign-label">SUPERVISOR:</span>
          <span class="sign-line"></span>
        </div>
      </div>

      <div class="note">
        註: 上述費用是按照《教育(豁免)(提供非正規課程的私立學校)令》所訂明的條件收取。<br>
        &nbsp;&nbsp;&nbsp;&nbsp;所收取的費用是按每月等額計算。如學校未能按預訂安排開辦課程，<br>
        &nbsp;&nbsp;&nbsp;&nbsp;便會按照課程單張所載的退款政策及程序，向上述學生退回全部或部分費用。
      </div>
    </div>
  </article>`
}

export function renderTuitionReceiptPrintWindow(printWindow: Window, data: TuitionReceiptPrintData) {
  const rows = [...data.lines]
  while (rows.length < MIN_ROWS)
    rows.push({ month: '', course: '', fee: null, qty: null, amount: null })

  const total = data.lines.reduce((sum, line) => sum + (line.amount ?? 0), 0)

  const lineRows = rows.map(line => `        <tr>
          <td>${escapeHtml(line.month)}</td>
          <td>${escapeHtml(line.course)}</td>
          <td class="num">${escapeHtml(formatMoney(line.fee))}</td>
          <td class="num">${escapeHtml(formatMoney(line.qty))}</td>
          <td class="num">${escapeHtml(formatMoney(line.amount))}</td>
        </tr>`).join('\n')

  const logoUrl = data.logoUrl || RECEIPT_LOGO_URL

  const logoCell = logoUrl
    ? `<div class="cell logo-cell"><img src="${escapeHtml(logoUrl)}" alt="logo" /></div>`
    : ''

  const header = data.header ?? DEFAULT_HEADER

  const centreLines = [
    header.regNo ? `<div class="reg">學校註冊編號: ${escapeHtml(header.regNo)}</div>` : '',
    header.address ? `<div>地址: ${escapeHtml(header.address)}</div>` : '',
    header.phone ? `<div>電話: ${escapeHtml(header.phone)}</div>` : '',
  ].filter(Boolean).join('\n        ')

  const copies = COPIES.map(copy =>
    receiptCopyHtml(data, copy.label, lineRows, total, logoCell, centreLines, header),
  ).join('\n')

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Receipt ${escapeHtml(data.receiptNo)} — ${escapeHtml(data.studentName)}</title>
  <style>
    * { box-sizing: border-box; }
    @page { size: A4 portrait; margin: 0; }
    html, body {
      background: #fff; color: #000; width: 210mm; height: 297mm; margin: 0; padding: 0;
    }
    body {
      font-family: "DFKai-SB", "標楷體", KaiTi, "Microsoft JhengHei", "PMingLiU", serif;
      font-size: 13px;
    }
    .sheet {
      position: relative; width: 210mm; height: 297mm; margin: 0 auto;
      padding: 8mm 12mm; display: flex; flex-direction: column;
    }
    .copy { flex: 1 1 0; min-height: 0; display: flex; flex-direction: column; justify-content: center; }
    .copy-inner { width: 100%; }
    .copy:first-of-type { padding-bottom: 10mm; }
    .copy:last-of-type { padding-top: 10mm; }
    .header { display: table; width: 100%; }
    .header > .cell { display: table-cell; vertical-align: top; }
    .logo-cell { width: 88px; padding-right: 10px; }
    .logo-cell img { max-width: 78px; max-height: 78px; }
    .centre { line-height: 1.35; }
    .centre .name-en { font-family: Arial, "Microsoft JhengHei", sans-serif; font-size: 17px; font-weight: 700; letter-spacing: 0.02em; }
    .centre .name-zh { font-size: 15px; font-weight: 700; }
    .centre .reg { font-size: 11px; }
    .title-cell { font-family: Arial, "Microsoft JhengHei", sans-serif; text-align: right; white-space: nowrap; width: 1%; }
    .title-cell .title { font-size: 22px; font-weight: 700; }
    .copy-label { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; margin-top: 2px; }
    .idrow { width: 100%; margin-top: 4px; line-height: 1.7; }
    .idrow .right { float: right; text-align: left; }
    .idrow .label { display: inline-block; min-width: 4.5em; }
    .fill { display: inline-block; min-width: 11em; border-bottom: 1px solid #000; text-align: right; padding: 0 4px; }
    .fill.wide { min-width: 16em; text-align: left; }
    .student { clear: both; margin-top: 2px; line-height: 1.7; }
    table.items { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 13px; }
    table.items th, table.items td { border: 1px solid #000; padding: 3px 8px; height: 22px; }
    table.items th { font-weight: 700; text-align: left; }
    table.items th.num, table.items td.num { text-align: right; white-space: nowrap; }
    .col-month { width: 16%; }
    .col-course { width: 36%; }
    .col-fee { width: 15%; }
    .col-qty { width: 13%; }
    .col-amount { width: 20%; }
    .total-row { width: 100%; margin-top: 0; }
    .total-row .amount {
      float: right; width: 20%; border: 1px solid #000; border-top: none;
      text-align: right; padding: 3px 8px; font-weight: 700;
    }
    .remark { clear: both; margin-top: 4px; line-height: 1.5; }
    .remark .label { display: inline-block; min-width: 3em; }
    .sign-row { clear: both; display: table; width: 100%; margin-top: 12px; }
    .sign-cell { display: table-cell; vertical-align: bottom; width: 62%; }
    .sign-cell.issued { width: 38%; padding-left: 16px; }
    .supervisor-row .sign-cell { width: 62%; }
    .sign-label { display: inline-block; min-width: 7.5em; }
    .sign-line {
      display: inline-block; min-width: 14em; border-bottom: 1px solid #000;
      padding: 0 4px; min-height: 1.3em;
    }
    .note { margin-top: 10px; font-size: 11px; line-height: 1.45; }
    .tear {
      position: absolute; left: 12mm; right: 12mm; top: 50%;
      transform: translateY(-50%); display: flex; flex-direction: column; gap: 8mm; pointer-events: none;
    }
    .tear-line { border-top: 2px dotted #000; width: 100%; }
    @media print {
      html, body, .sheet { width: 210mm; height: 100%; margin: 0; overflow: hidden; }
      .sheet { page-break-inside: avoid; page-break-after: avoid; }
    }
  </style>
</head>
<body>
<div class="sheet">
${copies}
  <div class="tear" aria-hidden="true">
    <div class="tear-line"></div>
    <div class="tear-line"></div>
  </div>
</div>
</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
}

export function printTuitionReceipt(printWindow: Window, data: TuitionReceiptPrintData) {
  renderTuitionReceiptPrintWindow(printWindow, data)
  printWindow.focus()
  printWindow.print()
}
