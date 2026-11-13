import type { TuitionInvoicePrintData } from '@/utils/printTuitionInvoice'

/** Served from `public/brands` and inlined before print. */
export const DRJ_DEBIT_NOTE_LOGO = '/brands/drj-logo.png'

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

/** Sample debit notes use M/D/YY, for example 8/19/26. */
function formatDebitDate(date: Date): string {
  if (Number.isNaN(date.getTime()))
    return ''

  const year = String(date.getFullYear()).slice(2)

  return `${date.getMonth() + 1}/${date.getDate()}/${year}`
}

/**
 * DRJ debit note. Letterhead and payment instructions are fixed company copy.
 * Per-invoice fields are bill-to, DN number, date, description lines, amounts, and total.
 */
export function buildDebitNotePrintHtml(data: TuitionInvoicePrintData): string {
  const rows = data.lines.filter(line => line.course.trim() || line.amount != null)

  const bodyRows = (rows.length ? rows : [{ course: '', amount: null }])
    .map(line => `        <tr>
          <td class="desc">${escapeHtml(line.course)}</td>
          <td class="amt">${escapeHtml(formatMoney(line.amount))}</td>
        </tr>`)
    .join('\n')

  const total = data.lines.reduce((sum, line) => sum + (line.amount ?? 0), 0)

  const logo = data.logoUrl
    ? `<img class="logo" src="${escapeHtml(data.logoUrl)}" alt="" />`
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
      padding: 14mm 16mm 12mm;
    }
    .letterhead {
      display: flex;
      align-items: flex-start;
      gap: 14px;
    }
    .logo {
      width: 72px;
      height: 72px;
      object-fit: contain;
      margin-top: 8px;
    }
    .identity { flex: 1 1 auto; text-align: center; }
    .brand {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 0.04em;
      margin: 0 0 10px;
    }
    .legal {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      margin: 0 0 2px;
    }
    .addr {
      margin: 0;
      line-height: 1.45;
      color: #222;
    }
    .meta {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-top: 22px;
      gap: 24px;
    }
    .billto .label {
      font-weight: 700;
      letter-spacing: 0.04em;
      margin-bottom: 6px;
    }
    .billto .name {
      min-height: 1.4em;
      font-size: 14px;
    }
    .refs { text-align: left; min-width: 220px; }
    .refs div { margin: 2px 0; }
    .refs .k {
      display: inline-block;
      width: 4.5em;
      font-weight: 700;
    }
    h1 {
      text-align: center;
      font-size: 16px;
      letter-spacing: 0.14em;
      margin: 18px 0 8px;
    }
    table.items {
      width: 100%;
      border-collapse: collapse;
    }
    table.items th, table.items td {
      border: 1px solid #111;
      vertical-align: top;
    }
    table.items th {
      text-align: center;
      font-weight: 700;
      padding: 6px 8px;
    }
    table.items td.desc {
      padding: 4px 8px;
      white-space: pre-wrap;
      line-height: 1.45;
    }
    table.items td.amt {
      width: 28%;
      text-align: right;
      padding: 4px 10px;
      white-space: nowrap;
    }
    table.items tbody tr { height: 22px; }
    .total-wrap {
      display: flex;
      justify-content: flex-end;
      margin-top: 10px;
    }
    .total {
      border: 1px solid #111;
      border-collapse: collapse;
    }
    .total td {
      border: 1px solid #111;
      padding: 4px 10px;
      font-weight: 700;
    }
    .total .amt { text-align: right; min-width: 110px; }
    .pay {
      margin-top: 16px;
      line-height: 1.45;
      max-width: 78%;
    }
    .pay .h { font-weight: 700; margin-bottom: 2px; }
    .foot {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-top: 28px;
      color: #6a6a6a;
      font-size: 11px;
      letter-spacing: 0.04em;
    }
    @media print {
      html, body, .sheet { width: 210mm; margin: 0; }
      .sheet { min-height: 0; }
    }
  </style>
</head>
<body>
  <div class="sheet">
    <header class="letterhead">
      ${logo}
      <div class="identity">
        <p class="brand">DRJ INTERNATIONAL | 施韋榮</p>
        <p class="legal">DRJ LIMITED</p>
        <p class="addr">Unit 1517, 15th Floor, Tower 2, Kowloon Commerce Centre,<br>
        No. 51 Kwai Cheong Road, Kwai Chung, New Territories, Hong Kong</p>
        <p class="addr">施韋榮有限公司<br>
        香港新界葵涌葵昌路51號九龍貿易中心<br>
        第2座15樓1517室<br>
        T 電話 +852 3700 0300</p>
      </div>
    </header>

    <div class="meta">
      <div class="billto">
        <div class="label">BILL TO:</div>
        <div class="name">${escapeHtml(data.studentName)}</div>
      </div>
      <div class="refs">
        <div><span class="k">DN NO:</span> ${escapeHtml(data.invoiceNo)}</div>
        <div><span class="k">DATE:</span> ${escapeHtml(formatDebitDate(data.issueDate))}</div>
      </div>
    </div>

    <h1>DEBIT NOTE</h1>

    <table class="items">
      <thead>
        <tr>
          <th>DESCRIPTION(S)</th>
          <th>AMOUNT (HK$)</th>
        </tr>
      </thead>
      <tbody>
${bodyRows}
      </tbody>
    </table>

    <div class="total-wrap">
      <table class="total">
        <tr>
          <td>Total HK$</td>
          <td class="amt">${escapeHtml(formatMoney(total))}</td>
        </tr>
      </table>
    </div>

    <div class="pay">
      <div class="h">Method of payment:</div>
      (1) Cheque payable to "DRJ Limited"/支票收款人請註明:「施韋榮有限公司」<br>
      (2) Payments by bank transfer to the following bank account:<br>
      A/C Name: DRJ Limited<br>
      Bank's Name: The Bank of East Asia, Limited<br>
      A/C No: 015-151-68-025137<br>
      Bank's Address: 10 Des Voeux Road, Central, Hong Kong<br>
      SWIFT Code: BEASHKHH<br>
      Clearing No.: 015 (for local interbank transfers)
    </div>

    <div class="foot">
      <div>THANK YOU FOR YOUR BUSINESS</div>
      <div>© ${year} For more information, contact DRJ</div>
    </div>
  </div>
</body>
</html>`
}
