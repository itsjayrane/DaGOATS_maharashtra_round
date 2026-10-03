export const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function req(path, opts = {}) {
  let res
  try {
    res = await fetch(API + path, {
      ...opts,
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    })
  } catch {
    throw new Error(`Cannot reach the backend at ${API}. Is it running?`)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* keep statusText */ }
    const e = new Error(detail)
    e.status = res.status
    throw e
  }
  return res.json()
}

export const api = {
  problems: () => req('/problems'),
  diagnose: (body) => req('/diagnose', { method: 'POST', body }),
  intervene: (label, extra = {}) => req('/intervene', { method: 'POST', body: { label, ...extra } }),
  transfer: (m, learnerId, exclude) =>
    req(`/transfer/${m}?learner_id=${encodeURIComponent(learnerId)}${exclude ? `&exclude=${exclude}` : ''}`),
  reassess: (body) => req('/reassess', { method: 'POST', body }),
  learner: (id) => req(`/learner/${encodeURIComponent(id)}`),
  health: () => req('/health'),
  explain: (body) => req('/explain', { method: 'POST', body }),
  metrics: () => req('/metrics'),
  hint: (body) => req('/hint', { method: 'POST', body }),
  confusionUrl: () => `${API}/metrics/confusion-matrix`,
}

export function learnerId() {
  try {
    let id = localStorage.getItem('relearn_learner')
    if (!id) {
      id = 'learner-' + Math.random().toString(36).slice(2, 10)
      localStorage.setItem('relearn_learner', id)
    }
    return id
  } catch {
    return 'learner-anon'
  }
}
