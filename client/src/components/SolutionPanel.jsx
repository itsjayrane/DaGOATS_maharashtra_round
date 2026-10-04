import { useEffect, useState } from 'react'
import { api } from '../api'
import { Button, CodeView, ErrorNote, Pill, RichText } from './ui'

// "Show solution" for every problem (built-in and own-question). The code is always the verified reference solution;
// the explanation is built-in or, when the server has an LLM configured, AI-written (and checked) - it says which.
// stage: 'hidden' | 'ask' (offer a hint first) | 'open'. compare = the learner already passed all tests.
export default function SolutionPanel({ problemId, learnerId, stage, compare, onHint, onShow }) {
  const [sol, setSol] = useState(null)
  const [error, setError] = useState('')
  const open = stage === 'open'

  useEffect(() => {
    if (!open || !problemId) return undefined
    let live = true
    api.getSolution(problemId, learnerId).then((s) => live && setSol(s)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [open, problemId, learnerId])

  if (stage === 'ask') {
    return (
      <div className="mt-4 rounded-lg border border-line bg-raised p-3" role="group" aria-label="Show the solution?">
        <p className="text-sm">Try a hint first? Working it out yourself helps it stick.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button onClick={onHint}>Get a hint</Button>
          <Button variant="ghost" onClick={onShow}>Show it anyway</Button>
        </div>
      </div>
    )
  }
  if (!open) return null
  if (error) return <div className="mt-4"><ErrorNote error={error} /></div>
  if (!sol) return <p className="mt-4 text-sm text-muted" role="status">Explaining…</p>

  const e = sol.explanation
  const ok = sol.verified.passed === sol.verified.total
  return (
    <section className="mt-4 space-y-4 rounded-xl border border-good/40 bg-good/5 p-4" aria-label={compare ? 'Compare with our solution' : 'Solution'} data-testid="solution">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold">{compare ? 'Compare with our solution' : 'Our solution'}</h3>
        <div className="flex flex-wrap gap-2">
          <Pill tone={ok ? 'good' : 'warn'}>Solution checked by running the tests · {sol.verified.passed}/{sol.verified.total}</Pill>
          {sol.source === 'ai' && <Pill tone="info">Explanation written by AI</Pill>}
        </div>
      </div>
      <CodeView code={sol.solution} tone="good" label="Solution (read-only)" />
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">In short</h4>
        <RichText text={e.summary} className="mt-1 text-sm text-ink/90" />
      </div>
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Step by step</h4>
        <ol className="mt-1 list-decimal space-y-1 pl-6 text-sm text-ink/90" data-testid="solution-steps">
          {e.steps.map((s, i) => <li key={i}><RichText text={s} className="inline" glossary={false} /></li>)}
        </ol>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-line bg-surface p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Key idea</h4>
          <RichText text={e.key_idea} className="mt-1 text-sm" />
        </div>
        <div className="rounded-lg border border-warn/40 bg-warn/10 p-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-warn">Watch out for</h4>
          <RichText text={e.common_mistake} className="mt-1 text-sm" glossary={false} />
        </div>
      </div>
      {sol.your_fix && (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Your code, fixed</h4>
          <CodeView code={sol.your_fix.code} highlight={sol.your_fix.changed_lines} tone="good" label="Your last attempt with the smallest change that works"
            caption={`Highlighted: the changed line(s). It passes all ${sol.your_fix.verified.total} tests.`} />
        </div>
      )}
    </section>
  )
}
