import { getQRToken } from '@/api/attendance/events'
import type { Unit } from '@/api/attendance/units'
import { formatApiError } from '@/utils/formatApiDetail'
import { toQrDataUrl } from '@/utils/qrCodeDataUrl'

export const UNIT_QR_CARD_IMAGE_SIZE = 152
export const UNIT_QR_PRINT_IMAGE_SIZE = 120

export interface UnitQrPrintItem {
  unit: Unit
  qrDataUrl: string
}

function typeLabel(type: string) {
  if (type === 'staff')
    return 'Staff'
  if (type === 'student')
    return 'Student'

  return type
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Call synchronously from a click handler before any await. */
export function openUnitQrPrintPlaceholder(): Window {
  const printWindow = window.open('about:blank', '_blank')
  if (!printWindow)
    throw new Error('Pop-up blocked. Allow pop-ups to print QR codes.')

  printWindow.document.open()
  printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>QR Codes</title></head>
<body style="font-family:system-ui,sans-serif;padding:24px;color:#333">
  <p>Preparing QR codes…</p>
</body></html>`)
  printWindow.document.close()

  return printWindow
}

export async function fetchUnitQrPrintItems(units: Unit[]): Promise<UnitQrPrintItem[]> {
  const results = await Promise.all(
    units.map(async (unit) => {
      const { qr_token } = await getQRToken(unit.id)
      const qrDataUrl = await toQrDataUrl(qr_token, UNIT_QR_PRINT_IMAGE_SIZE)

      return { unit, qrDataUrl }
    }),
  )

  return results
}

function waitForImages(doc: Document): Promise<void> {
  const images = Array.from(doc.images)
  if (!images.length)
    return Promise.resolve()

  return Promise.all(
    images.map(img => new Promise<void>((resolve) => {
      if (img.complete) {
        resolve()

        return
      }
      img.addEventListener('load', () => resolve(), { once: true })
      img.addEventListener('error', () => resolve(), { once: true })
    })),
  ).then(() => undefined)
}

export function renderUnitQrPrintWindow(printWindow: Window, items: UnitQrPrintItem[]) {
  if (!items.length)
    return

  const cards = items.map(({ unit, qrDataUrl }) => `
    <section class="print-card">
      <img src="${qrDataUrl}" alt="QR for ${escapeHtml(unit.full_name)}" width="${UNIT_QR_PRINT_IMAGE_SIZE}" height="${UNIT_QR_PRINT_IMAGE_SIZE}" style="width:2.3cm;height:2.3cm" />
      <h2>${escapeHtml(unit.full_name)}</h2>
      <p class="code">${escapeHtml(unit.code)}</p>
      <p class="meta">${escapeHtml(typeLabel(unit.unit_type))}</p>
    </section>
  `).join('')

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>QR Codes (${items.length})</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      margin: 0;
      padding: 16px;
      color: #111;
    }
    h1 {
      font-size: 18px;
      margin: 0 0 16px;
      font-weight: 600;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      justify-items: center;
      gap: 24px;
    }
    .print-card {
      border: 1px solid #ccc;
      border-radius: 8px;
      padding: 6px;
      width: 3.5cm;
      text-align: center;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .print-card img {
      display: block;
      margin: 0 auto 6px;
      border: 3px solid #333;
      border-radius: 4px;
    }
    .print-card h2 {
      font-size: 14px;
      margin: 0 0 4px;
      line-height: 1.3;
    }
    .print-card .code {
      font-size: 10px;
      margin: 0 0 4px;
      color: #444;
    }
    .print-card .meta {
      font-size: 9px;
      margin: 0;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    @media print {
      body { padding: 0; }
      h1 { display: none; }
      .grid {
        grid-template-columns: repeat(4, 1fr);
        justify-items: center;
        gap: 20px;
      }
    }
  </style>
</head>
<body>
  <h1>QR Codes — ${items.length} unit${items.length === 1 ? '' : 's'}</h1>
  <div class="grid">${cards}</div>
</body>
</html>`

  printWindow.document.open()
  printWindow.document.write(html)
  printWindow.document.close()
}

export async function printUnitQrs(units: Unit[], printWindow: Window) {
  if (!units.length)
    return

  try {
    const items = await fetchUnitQrPrintItems(units)

    renderUnitQrPrintWindow(printWindow, items)
    await waitForImages(printWindow.document)
    printWindow.focus()
    printWindow.print()
  }
  catch (e) {
    printWindow.document.open()
    printWindow.document.write(`<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;padding:24px;color:#b00020">
  <p><strong>Could not print QR codes.</strong></p>
  <p>${escapeHtml(formatApiError(e, 'Unknown error'))}</p>
</body></html>`)
    printWindow.document.close()
    throw new Error(formatApiError(e, 'Could not prepare QR codes for printing'))
  }
}
