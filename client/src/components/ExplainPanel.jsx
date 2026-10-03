import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, CodeView, ErrorNote, Pill } from './ui'

function Step({ n, title, children }) {
  return (
    <section className="flex gap-3" aria-label={title}>
      <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-sm font-bold text-accent" aria-hidden>{n}</span>
      <div className="min-w-0 flex-1">
        <h3 className="font-semibold">{title}</h3>
        <div className="mt-1">{children}</div>
      </div>
    </section>
  )
}

// The student explanation card (POST /explain, deterministic): what went wrong -> why -> your code fixed -> best solution.
// A fix of the learner's own code is shown only if it passes every test.
export default function ExplainPanel({ problemId, code, label }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    api.explain({ problem_id: problemId, code, label: label || undefined }).then((d) => live && setData(d)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [problemId, code, label])

  if (error) return <Card title="Your explanation"><ErrorNote error={error} /></Card>
  if (!data) return <Card title="Your explanation"><p className="text-sm text-muted">Working out what went wrong…</p></Card>
  if (data.all_tests_pass) return null
  const w = data.where_it_went_wrong
  const fix = data.proposed_fix
  return (
    <Card title="Your explanation" right={<Pill tone={label ? 'info' : 'warn'}>{data.why?.name || 'step by step'}</Pill>}>
      <div className="space-y-5">
        <Step n={1} title="What went wrong">
          {w && <p className="text-sm leading-relaxed text-ink" data-testid="explain-where">{w.words}</p>}
          {w?.technical && (
            <details className="mt-2 text-sm text-muted">
              <summary className="min-h-[44px] cursor-pointer py-2">Technical details</summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{w.technical}</pre>
            </details>
          )}
        </Step>
        <Step n={2} title="Why">
          <p className="text-sm leading-relaxed text-ink/90" data-testid="explain-why">{data.why?.text}</p>
        </Step>
        <Step n={3} title="Your code, fixed">
          {fix ? (
            <CodeView code={fix.code} highlight={fix.fixed_highlight_lines} tone="good" label="Your code with the smallest change that works"
              caption={`Only the highlighted line(s) changed - it now passes all ${fix.verified.total} tests.`} />
          ) : (
            <p className="text-sm text-muted">We could not find a small change to your code that passes every test, so compare it with the best solution below.</p>
          )}
        </Step>
        {data.best_solution && (
          <Step n={4} title="Best solution">
            <CodeView code={data.best_solution.code} tone="good" label="A clear, correct solution" caption={data.best_solution.reason} />
          </Step>
        )}
      </div>
    </Card>
  )
}
