import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, CodeView, ErrorNote, Pill } from './ui'

// Deterministic explanation from POST /explain: what went wrong, a verified fix of the learner's code (if one exists),
// and a verified best solution. Used when the model is not sure which common mistake this is.
export default function ExplainPanel({ problemId, code }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    api.explain({ problem_id: problemId, code }).then((d) => live && setData(d)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [problemId, code])

  if (error) return <Card title="What happened"><ErrorNote error={error} /></Card>
  if (!data) return <Card title="What happened"><p className="text-sm text-muted">Working out what went wrong…</p></Card>
  const w = data.where_it_went_wrong
  return (
    <Card title="What happened" right={<Pill tone="warn">explained step by step</Pill>}>
      {w && <p className="text-sm leading-relaxed text-ink" data-testid="explain-where">{w.words}</p>}
      {w?.technical && (
        <details className="mt-2 text-xs text-muted"><summary className="cursor-pointer">Technical details</summary><pre className="mt-1 whitespace-pre-wrap font-mono">{w.technical}</pre></details>
      )}
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {data.proposed_fix && (
          <CodeView code={data.proposed_fix.code} highlight={data.proposed_fix.fixed_highlight_lines} tone="good" label="Your code, fixed"
            caption={`Only the highlighted lines changed - it passes all ${data.proposed_fix.verified.total} tests.`} />
        )}
        {data.best_solution && (
          <CodeView code={data.best_solution.code} tone="good" label="Best solution" caption={data.best_solution.reason} />
        )}
      </div>
    </Card>
  )
}
