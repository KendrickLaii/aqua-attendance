/**
 * Copy text using a synchronous DOM path first (preserves user activation in
 * strict browsers), then the Async Clipboard API.
 */
function copyViaExecCommand(text: string): boolean {
  if (typeof document === 'undefined' || !text)
    return false

  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.top = '0'
    ta.style.left = '0'
    ta.style.opacity = '0'
    ta.style.pointerEvents = 'none'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    ta.remove()

    return ok
  }
  catch {
    return false
  }
}

/**
 * Best-effort clipboard copy for production (HTTPS, various mobile browsers).
 * Returns true if something reported success.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text)
    return false

  if (copyViaExecCommand(text))
    return true

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && typeof window !== 'undefined' && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)

      return true
    }
    catch {
      // ignore
    }
  }

  return false
}
