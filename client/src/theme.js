import { useEffect, useState } from 'react'

const KEY = 'relearn-theme'
const EVENT = 'relearn-theme'

export function storedTheme() {
  try { return localStorage.getItem(KEY) } catch { return null }
}

export function currentTheme() {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

export function applyTheme(t) {
  document.documentElement.dataset.theme = t
  try { localStorage.setItem(KEY, t) } catch { /* private mode: the choice lasts until reload */ }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: t }))
}

export function useTheme() {
  const [t, setT] = useState(currentTheme)
  useEffect(() => {
    const f = (e) => setT(e.detail)
    window.addEventListener(EVENT, f)
    return () => window.removeEventListener(EVENT, f)
  }, [])
  return [t, applyTheme]
}

// "seen" flags for one-time things like the onboarding
export function flag(name) {
  try { return localStorage.getItem(`relearn-${name}`) === '1' } catch { return false }
}
export function setFlag(name, on = true) {
  try { if (on) localStorage.setItem(`relearn-${name}`, '1'); else localStorage.removeItem(`relearn-${name}`) } catch { /* ignore */ }
}
