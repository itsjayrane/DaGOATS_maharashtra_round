import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, CodeBlock, ErrorNote, Pill } from './ui'
import { plain } from '../labels'

// Twin probe: when two look-alike mistakes are close, one predict-the-output question tells them apart.
// onPick(label) is called when the answer points to one of the two mistakes.
export default function QuickCheck({ a, b, learnerId, problemId, current, onPick }) {
  const [probe, setProbe] = useState(null)
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    api.probe(a, b, learnerId).then((p) => live && setProbe(p)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [a, b, learnerId])

  const answer = async (i) => {
    try {
      const r = await api.probeAnswer({ probe_id: probe.probe_id, choice: i, learner_id: learnerId, problem_id: problemId })
      setRes({ ...r, choice: i })
      if (r.suggested_label && r.suggested_label !== current) onPick(r.suggested_label)
    } catch (e) { setError(e.message) }
  }

  if (error) return <Card title="Quick check"><ErrorNote error={error} /></Card>
  if (!probe) return null
  return (
    <Card title="Quick check" right={<Pill tone="warn">helps us pick the right lesson</Pill>}>
      <p className="text-sm text-ink/90">
        Your code fits two look-alike mistakes: “{plain(a)}” and “{plain(b)}”. One quick question tells them apart. {probe.question}
      </p>
      <div className="mt-3"><CodeBlock code={probe.code} label="Code" /></div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Quick check answers">
        {probe.options.map((o, i) => {
          const state = !res ? 'border-line hover:border-accent' : o === res.answer ? 'border-good bg-good/10' : i === res.choice ? 'border-bad bg-bad/10' : 'border-line opacity-60'
          return (
            <button key={i} type="button" role="radio" aria-checked={res?.choice === i} disabled={!!res} onClick={() => answer(i)}
              className={`min-h-[44px] rounded-lg border px-3 py-2 text-left font-mono text-sm transition ${state}`}>{o}</button>
          )
        })}
      </div>
      {res && (
        <div className="mt-3 text-sm" role="status" data-testid="quick-check-result">
          <p className={res.correct ? 'text-good' : 'text-warn'}>{res.correct ? 'Right! ' : `The answer is ${res.answer}. `}<span className="text-ink/90">{res.explanation}</span></p>
          {res.suggested_label && (
            <p className="mt-1 font-semibold">
              {res.suggested_label === current ? `That matches what we found: “${plain(current)}”.` : `Your answer points to “${plain(res.suggested_label)}” - the lesson below now covers that one.`}
            </p>
          )}
          {!res.suggested_label && !res.correct && <p className="mt-1 text-muted">Your answer fits both ideas, so keep both in mind in the lesson below.</p>}
        </div>
      )}
    </Card>
  )
}
