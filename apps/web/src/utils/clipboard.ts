export async function copyTextToClipboard(text: string): Promise<void> {
  // Primary path: modern Clipboard API
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return
    }
  }
  catch {
    // Continue to fallback
  }

  // Fallback: execCommand('copy')
  if (typeof document === 'undefined')
    throw new Error('Clipboard fallback requires document')

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  textarea.style.left = '-9999px'
  textarea.style.opacity = '0'

  document.body.appendChild(textarea)
  textarea.select()
  textarea.setSelectionRange(0, textarea.value.length)

  const ok = document.execCommand('copy')
  document.body.removeChild(textarea)

  if (!ok)
    throw new Error('Fallback copy failed')
}

