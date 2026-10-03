import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { HealthContext, useServerHealth } from '../serverHealth'

const DELAYS = [1000, 2000, 3000, 5000, 8000] // then 8 s steps
const GIVE_UP_MS = 90000

export function ServerHealthProvider({ children }) {
  const [status, setStatus] = useState('checking')
  const [run, setRun] = useState(0)
  const timer = useRef(null)

  useEffect(() => {
    let cancelled = false
    const started = Date.now()
    const attempt = async (n) => {
      try {
        const h = await api.health()
        if (!cancelled && h?.ok) { setStatus('up'); return }
      } catch { /* server asleep or starting */ }
      if (cancelled) return
      if (Date.now() - started > GIVE_UP_MS) { setStatus('down'); return }
      setStatus('waking')
      timer.current = setTimeout(() => attempt(n + 1), DELAYS[Math.min(n, DELAYS.length - 1)])
    }
    attempt(0)
    return () => { cancelled = true; clearTimeout(timer.current) }
  }, [run])

  const retry = useCallback(() => setRun((r) => r + 1), [])
  return <HealthContext.Provider value={{ status, healthy: status === 'up', retry }}>{children}</HealthContext.Provider>
}

export function ServerBanner() {
  const { status, retry } = useServerHealth()
  if (status === 'up' || status === 'checking') return null
  return (
    <div role="status" aria-live="polite" className="border-b border-warn/40 bg-warn/10 px-4 py-2 text-center text-sm text-warn">
      {status === 'waking'
        ? 'Waking the server (up to ~60 s)… The free hosting plan sleeps when nobody is using it.'
        : <>The server is not answering right now. <button type="button" onClick={retry} className="underline">Try again</button></>}
    </div>
  )
}
