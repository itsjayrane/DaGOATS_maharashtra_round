import { useEffect, useState } from 'react'
import { api } from '../api'
import { Button, Card, CodeBlock, ErrorNote, Pill, RichText } from './ui'

export default function InterventionPanel({ label, onProve }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)

  useEffect(() => {
    let live = true
    api.intervene(label).then((d) => live && setData(d)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [label])

  if (error) return <Card title="Targeted intervention"><ErrorNote error={error} /></Card>
  if (!data?.intervention) return <Card title="Targeted intervention"><p className="text-sm text-muted">Loading…</p></Card>
  const iv = data.intervention
  const q = iv.predict
  const answered = picked !== null
  const right = picked === q.answer

  return (
    <Card title="Targeted intervention" right={<Pill tone="info">{data.name}</Pill>}>
      <h3 className="text-lg font-semibold">{iv.title}</h3>
      <RichText text={iv.explanation} className="mt-2 text-sm text-ink/90" />

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <CodeBlock code={iv.wrong_code} tone="bad" label="✗ What you did" />
        <CodeBlock code={iv.right_code} tone="good" label="✓ What works" />
      </div>

      <div className="mt-5">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Trace it</h4>
        <ol className="space-y-1 rounded-lg border border-line bg-[#0d1320] p-3 font-mono text-[13px]">
          {iv.trace.map((s, i) => <li key={i} className="text-ink/90"><span className="mr-2 text-muted">{i + 1}.</span>{s}</li>)}
        </ol>
      </div>

      <div className="mt-6 rounded-lg border border-line bg-raised p-4">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Concept check</h4>
        <pre className="mb-3 whitespace-pre-wrap font-mono text-[13px] text-ink">{q.question}</pre>
        <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Concept check answers">
          {q.options.map((o, i) => {
            const state = !answered ? 'border-line hover:border-accent' : i === q.answer ? 'border-good bg-good/10' : i === picked ? 'border-bad bg-bad/10' : 'border-line opacity-60'
            return (
              <button key={i} role="radio" aria-checked={picked === i} disabled={answered} onClick={() => setPicked(i)}
                className={`rounded-lg border px-3 py-2 text-left font-mono text-sm transition ${state}`}>{o}</button>
            )
          })}
        </div>
        {answered && (
          <p className={`mt-3 text-sm ${right ? 'text-good' : 'text-bad'}`}>
            {right ? 'Right. ' : 'Not quite. '}<span className="text-ink/90">{q.explanation}</span>
          </p>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        <p className="text-xs text-muted">A correct answer here isn't enough - next you'll solve a different problem to prove it.</p>
        <Button disabled={!answered} onClick={onProve}>Prove it →</Button>
      </div>
    </Card>
  )
}
