import { ErrorNote, Pill, RichText } from './ui'

export const MAX_HINTS = 3

// why a built-in hint was shown instead of an AI one (reason codes come from the backend)
const WHY = {
  no_api_key: 'AI not configured', rate_limited: 'AI rate limit reached', overloaded: 'AI busy right now', timeout: 'AI timed out',
  api_error: 'AI request failed', bad_response: 'AI answer unusable', guardrail_rejected: 'AI answer filtered',
}

// Hints revealed so far (one per level), a loading line while the next one is on its way, and notes/errors.
export default function HintPanel({ hints, loading, note, error }) {
  if (!hints.length && !loading && !note && !error) return null
  return (
    <div className="mt-4 space-y-3 rounded-lg border border-line bg-raised p-4" role="region" aria-label="Hints" aria-live="polite" data-testid="hint-panel">
      {hints.map((h) => (
        <div key={h.level} data-testid="hint-item">
          <div className="mb-1 flex items-center gap-2">
            <Pill tone="info">Hint {h.level}/{MAX_HINTS}</Pill>
            <span className="text-[11px] text-muted">{h.source === 'llm' ? 'AI hint' : `built-in hint · ${WHY[h.reason] ?? 'AI unavailable'}`}</span>
          </div>
          <RichText text={h.hint} className="text-sm text-ink/90" />
        </div>
      ))}
      {loading && <p className="text-sm text-muted" data-testid="hint-loading">Thinking of hint {hints.length + 1}/{MAX_HINTS}…</p>}
      {note && <p className="text-sm text-good" data-testid="hint-note">{note}</p>}
      <ErrorNote error={error} />
      {hints.length >= MAX_HINTS && <p className="text-xs text-muted">That's all three hints. Still stuck? Submit your code to get a diagnosis and a targeted lesson.</p>}
    </div>
  )
}
