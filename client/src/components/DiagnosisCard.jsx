import { Bar, Card, Pill } from './ui'
import { plain, short, STATUS, testSentence } from '../labels'

// Test results as sentences ("sum_list([1, 2]) should give 3, but your code gave 1."), errors in plain English.
export function TestResults({ tests, fn = 'f' }) {
  if (!tests?.length) return null
  return (
    <ul className="space-y-2 text-sm" data-testid="test-sentences">
      {tests.map((t, i) => {
        const s = testSentence(fn, t)
        return (
          <li key={i} className="flex gap-2">
            <span className={`shrink-0 font-bold ${s.ok ? 'text-good' : 'text-bad'}`} aria-label={s.ok ? 'passed' : 'failed'}>{s.ok ? '✓' : '✗'}</span>
            <span className="min-w-0">
              <span className={s.ok ? 'text-ink/90' : 'text-ink'}>{s.text}</span>
              {s.technical && (
                <details className="mt-1 text-xs text-muted">
                  <summary className="cursor-pointer">Technical details</summary>
                  <code className="font-mono">{s.technical}</code>
                </details>
              )}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export default function DiagnosisCard({ diag, fn }) {
  const ok = diag.verdict ? diag.verdict === 'correct' : diag.label === 'CORRECT'
  const unsure = diag.unknown && diag.label
  const tone = ok ? 'good' : unsure ? 'warn' : diag.label ? 'bad' : 'warn'
  const top = diag.probabilities
    ? Object.entries(diag.probabilities).sort((a, b) => b[1] - a[1]).slice(0, 3)
    : []
  const n = diag.test_results?.length ?? 0
  const passed = diag.test_results?.filter((t) => t.ok).length ?? 0
  const pill = ok ? 'All tests pass' : unsure ? 'Not sure' : diag.label ? plain(diag.label) : 'Could not check'
  return (
    <Card title="What we found" right={<Pill tone={tone}>{pill}</Pill>}>
      {!diag.label ? (
        <div>
          <p className="text-sm text-warn">{STATUS[diag.status] || diag.error || 'Your code could not be checked.'}</p>
          {diag.error && STATUS[diag.status] && (
            <details className="mt-2 text-sm text-muted">
              <summary className="min-h-[44px] cursor-pointer py-2">Technical details</summary>
              <pre className="whitespace-pre-wrap font-mono text-xs">{diag.error}</pre>
            </details>
          )}
        </div>
      ) : (
        <div className="space-y-5">
          {ok ? (
            <div className="celebrate rounded-lg border border-good/40 bg-good/10 p-4" data-testid="celebrate">
              <p className="text-lg font-bold text-good"><span aria-hidden>🎉 </span>Correct - all {n} tests pass!</p>
              <p className="mt-1 text-sm text-ink/90">Nice work. Try the recommended next problem to keep going.</p>
            </div>
          ) : unsure ? (
            <div className="rounded-lg border border-warn/40 bg-warn/10 p-3" data-testid="unsure">
              <p className="font-semibold text-warn">
                Not sure{diag.closest_guess ? ` — closest guess: ${plain(diag.closest_guess.label)} (${Math.round(diag.closest_guess.probability * 100)}%)` : ''}
              </p>
              <p className="mt-1 text-sm text-ink/90">{diag.unknown_reason} So instead of a lesson that might not fit, here is exactly what went wrong.</p>
            </div>
          ) : (
            <div>
              <p className="text-lg font-semibold">Likely mistake: {plain(diag.label)}</p>
              <div className="mt-3">
                <Bar value={diag.confidence} tone={tone} label="How sure we are" right={`${Math.round(diag.confidence * 100)}%`} />
              </div>
              {diag.ambiguous && diag.runner_up && (
                <p className="mt-2 text-sm text-warn">
                  It could also be “{plain(diag.runner_up.label)}” ({Math.round(diag.runner_up.probability * 100)}%) - these two can look alike.
                </p>
              )}
            </div>
          )}
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
              Tests {n ? `· ${passed} of ${n} passing` : ''}
            </h3>
            <TestResults tests={diag.test_results} fn={fn} />
          </div>
          {!ok && (
            <details className="text-sm">
              <summary className="min-h-[44px] cursor-pointer py-2 text-muted">How we decided (technical details)</summary>
              <ul className="mt-1 space-y-1.5">
                {diag.evidence.map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <span className={e.kind === 'behavior' ? 'text-warn' : 'text-accent'} aria-hidden>●</span>
                    <span className="text-ink/90">{e.text}</span>
                  </li>
                ))}
              </ul>
              {top.length > 1 && (
                <p className="mt-2 text-xs text-muted">Model scores: {top.map(([l, p]) => `${short(l)} ${Math.round(p * 100)}%`).join(' · ')}</p>
              )}
            </details>
          )}
        </div>
      )}
    </Card>
  )
}
