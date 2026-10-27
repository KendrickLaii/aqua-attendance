export function readAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error ?? new Error('Could not read logo'))
    reader.readAsDataURL(blob)
  })
}

/** Embed the logo so the print document does not depend on a second request. */
export async function inlineLogoForPrint(url: string): Promise<string> {
  if (!url || url.startsWith('data:'))
    return url

  try {
    const response = await fetch(url)
    if (!response.ok)
      return url

    return (await readAsDataUrl(await response.blob())) || url
  }
  catch {
    return url
  }
}

export function waitForImages(doc: Document): Promise<void> {
  const images = Array.from(doc.images)
  const loaded = Promise.all(images.map(async img => {
    if (!img.complete) {
      await new Promise<void>(resolve => {
        img.addEventListener('load', () => resolve(), { once: true })
        img.addEventListener('error', () => resolve(), { once: true })
      })
    }
    if (typeof img.decode === 'function')
      await img.decode().catch(() => undefined)
  })).then(() => undefined)

  const timeout = new Promise<void>(resolve => {
    window.setTimeout(resolve, 2500)
  })

  return Promise.race([loaded, timeout])
}

export function printFromWindow(printWindow: Window): Promise<void> {
  return new Promise(resolve => {
    const script = printWindow.document.createElement('script')

    // Run inside the invoice window. Edge ignores print() that the opener
    // calls before this document has finished painting.
    script.textContent = `
      window.setTimeout(function () {
        var paint = window.requestAnimationFrame
          ? window.requestAnimationFrame.bind(window)
          : function (cb) { window.setTimeout(cb, 16) }
        paint(function () {
          paint(function () {
            window.focus()
            window.print()
          })
        })
      }, 50)
    `
    printWindow.document.body.appendChild(script)
    window.setTimeout(resolve, 300)
  })
}
