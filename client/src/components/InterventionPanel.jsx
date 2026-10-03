import { useEffect, useState } from 'react'
import { api } from '../api'
import { Button, Card, CodeBlock, CodeView, ErrorNote, Pill, RichText } from './ui'

function Contrast({ p, generic }) {
  // p = personalised payload for THIS learner's code; falls back to the generic example only if it could not be built
  if (!p) {
    return (
      <div className="grid gap-3 md:grid-cols-2">
        <CodeBlock code={generic.wrong_code} tone="bad" label="✗ What goes wrong (generic example)" />
        <CodeBlock code={generic.right_code} tone="good" label="✓ What works" />
      </div>
    )
  }
  const auto = p.source === 'auto_fix'
  const ok = p.verified.passed === p.verified.total
  const badge = (
    <span className={`text-xs font-medium ${ok ? 'text-good' : 'text-warn'}`}>
      {ok ? '✓' : '!'} passes {p.verified.passed}/{p.verified.total} tests
    </span>
  )
  return (
    <div>
      <div className="grid gap-3 md:grid-cols-2">
        <CodeView code={p.your_code} highlight={p.highlight_lines} tone="bad" label="✗ What you did"
          caption={p.highlight_lines.length ? 'Your submitted code. Highlighted: the line(s) that cause it.' : 'Your submitted code.'} />
        <CodeView code={p.fixed_code} highlight={p.fixed_highlight_lines} tone="good"
          label={auto ? '✓ What works - your code, minimally fixed' : '✓ What works - a correct solution'} badge={badge}
          caption={auto ? 'Only the misconception was changed; highlighted lines differ from yours.' : 'We could not safely fix your code with a small edit, so this is a correct solution to the same problem.'} />
      </div>
      <p className="mt-3 text-sm text-ink/90" data-testid="fix-rule">
        <span className="font-semibold text-accent">{auto ? 'The fix: ' : 'Why a different solution: '}</span>
        <span>{auto ? p.rule : p.rule}</span>
      </p>
      {p.identical && <p className="mt-1 text-xs text-warn">Your code already matches the only correct solution we have for this problem.</p>}
    </div>
  )
}

export default function InterventionPanel({ label, problemId, code, learnerId, onProve }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [picked, setPicked] = useState(null)

  useEffect(() => {
    let live = true
    api.intervene(label, { problem_id: problemId, code, learner_id: learnerId })
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [label, problemId, code, learnerId])

  if (error) return <Card title="Targeted intervention"><ErrorNote error={error} /></Card>
  if (!data?.intervention) return <Card title="Targeted intervention"><p className="text-sm text-muted">Building a fix for your code…</p></Card>
  const iv = data.intervention
  const q = iv.predict
  const answered = picked !== null
  const right = picked === q.answer

  return (
    <Card title="Targeted intervention" right={<Pill tone="info">{data.name}</Pill>}>
      <h3 className="text-lg font-semibold">{iv.title}</h3>
      <RichText text={iv.explanation} className="mt-2 text-sm text-ink/90" />

      <div className="mt-5"><Contrast p={data.personalized} generic={iv} /></div>

      <div className="mt-6 rounded-lg border border-line bg-raised/60 p-4">
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Concept example</h4>
        <p className="mb-3 text-xs text-muted">The same idea in a tiny, general example - not your code.</p>
        <div className="grid gap-3 md:grid-cols-2">
          <CodeBlock code={iv.wrong_code} tone="bad" label="✗ misconception" />
          <CodeBlock code={iv.right_code} tone="good" label="✓ idea" />
        </div>
        <ol className="mt-3 space-y-1 rounded-lg border border-line bg-[#0d1320] p-3 font-mono text-[12px]">
          {iv.trace.map((s, i) => <li key={i} className="text-ink/90"><span className="mr-2 text-muted">{i + 1}.</span>{s}</li>)}
        </ol>
      </div>

      <div className="mt-6 rounded-lg border border-line bg-raised p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Concept check</h4>
          <span className="text-xs text-muted">{data.concept_source === 'fallback_pool' ? 'general practice question' : data.concept_source === 'llm' ? 'about your code · AI-written, answer verified' : data.personalized ? 'about your code' : ''}</span>
        </div>
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
