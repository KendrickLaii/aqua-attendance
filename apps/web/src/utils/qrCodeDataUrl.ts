import QRCode from 'qrcode'

/** Render QR as a data URL locally (token never sent to a third party). */
export async function toQrDataUrl(text: string, sizePx = 280): Promise<string> {
  if (!text)
    return ''

  return QRCode.toDataURL(text, {
    width: sizePx,
    margin: 2,
    errorCorrectionLevel: 'M',
  })
}
