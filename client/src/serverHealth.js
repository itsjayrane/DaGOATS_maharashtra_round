import { createContext, useContext } from 'react'

// 'checking' -> 'up' | 'waking' (retrying with backoff) | 'down' (gave up after ~90 s; the user can retry)
export const HealthContext = createContext({ status: 'checking', healthy: false, retry: () => {} })
export const useServerHealth = () => useContext(HealthContext)
