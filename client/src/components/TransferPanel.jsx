import { useEffect, useState } from 'react'
import { api } from '../api'
import CodeEditor from './CodeEditor'
import { TestResults } from './DiagnosisCard'
import { Bar, Button, Card, ErrorNote, Pill, RichText } from './ui'
import { plain, short } from '../labels'

const CHECKS = {
  new_task: 'A new problem (not the one where we found the mistake)',
  tests_pass: 'All tests pass',
  misconception_not_detected: 'The mistake did not come back',
  concept_answer: 'Concept question answered correctly',
  enough_evidence: 'Enough proof: 2 different problems',
}

function Result({ r, fn }) {
  const tone = r.resolved ? 'good' : 'warn'
  return (
    <div className={`rounded-xl border p-4 ${r.resolved ? 'border-good/40 bg-good/10' : 'border-warn/40 bg-warn/10'}`} role="status">
      <div className="flex items-center justify-between gap-3">
        <p className={`text-xl font-bold ${r.resolved ? 'celebrate text-good' : 'text-warn'}`} data-testid={r.resolved ? 'resolved' : undefined}>
          {r.resolved ? <><span aria-hidden>🏆 </span>Fixed for good!</> : 'Not yet'}
        </p>
        {r.mastery_after != null && <Pill tone={tone}>mastery {Math.round(r.mastery_after * 100)}%</Pill>}
      </div>
      <p className="mt-1 text-sm text-ink/90">{r.resolved ? `“${plain(r.misconception)}” is now in your skills you've fixed.` : r.message}</p>
      <ul className="mt-4 space-y-2 text-sm">
        {r.reasons.map((x) => (
          <li key={x.check} className="flex gap-2">
            <span className={x.passed ? 'text-good' : 'text-bad'} aria-label={x.passed ? 'passed' : 'failed'}>{x.passed ? '✓' : '✗'}</span>
            <span><span className="font-medium">{CHECKS[x.check] || x.check.replaceAll('_', ' ')}</span> <span className="text-muted">- {x.detail}</span></span>
          </li>
        ))}
      </ul>
      {r.concept_explanation && <p className="mt-3 text-sm text-warn">{r.concept_explanation}</p>}
      {!r.resolved && r.test_results?.length > 0 && <div className="mt-4"><TestResults tests={r.test_results} fn={fn} /></div>}
    </div>
  )
}

const fnOf = (info, r) => info?.problems.find((p) => p.id === r?.problem_id)?.function

export default function TransferPanel({ label, learnerId, originalProblemId, onResolved }) {
  const [info, setInfo] = useState(null)
  const [pid, setPid] = useState(null)
  const [code, setCode] = useState('')
  const [qi, setQi] = useState(0)
  const [answer, setAnswer] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [cleared, setCleared] = useState([])
  const [advanced, setAdvanced] = useState('')

  useEffect(() => {
    let live = true
    api.transfer(short(label), learnerId, originalProblemId)
      .then((d) => { if (!live) return; setInfo(d); setPid(d.problems[0]?.id ?? null); setCode(d.problems[0]?.starter ?? '') })
      .catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [label, learnerId, originalProblemId])

  const problem = info?.problems.find((p) => p.id === pid)
  const q = info?.concept_questions[qi]

  const choose = (id) => {
    const p = info.problems.find((x) => x.id === id)
    setPid(id); setCode(p.starter); setResult(null); setAdvanced('')
  }
  const submit = async () => {
    setBusy(true); setError(''); setResult(null); setAdvanced('')
    try {
      const r = await api.reassess({ learner_id: learnerId, misconception: short(label), problem_id: pid, code, concept_answer: answer, concept_id: q.id })
      setResult({ ...r, problem_id: pid })
      if (r.cleared_problems) setCleared(r.cleared_problems)
      if (r.resolved) onResolved?.()
      else if (r.cleared_problems?.includes(pid)) {
        // this one is cleared: move straight on to a different transfer problem (the same one never counts twice)
        const next = info.problems.find((x) => !r.cleared_problems.includes(x.id))
        if (next) {
          setPid(next.id); setCode(next.starter); setAnswer(null)
          setAdvanced(`Cleared! Next problem loaded: ${next.title}.`)
        }
      }
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (error && !info) return <Card title="Prove it"><ErrorNote error={error} /></Card>
  if (!info) return <Card title="Prove it"><p className="text-sm text-muted">Loading transfer problems…</p></Card>

  return (
    <Card title="Prove it · transfer problems" right={<Pill tone={cleared.length >= (result?.needed ?? 2) ? 'good' : 'info'}>{Math.min(cleared.length, result?.needed ?? 2)} / {result?.needed ?? 2} cleared</Pill>}>
      <p className="mb-1 text-sm font-semibold">Mistake to beat: {plain(label)}</p>
      <p className="mb-4 text-sm text-muted">
        Solve 2 different fresh problems where the same idea matters. Each one counts when its tests pass, the mistake does not
        come back, and you answer the concept question correctly.
      </p>

      <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label="Transfer problems">
        {info.problems.map((p) => (
          <button key={p.id} role="tab" aria-selected={p.id === pid} onClick={() => choose(p.id)}
            className={`min-h-[44px] rounded-lg border px-3 py-1.5 text-sm font-medium transition ${p.id === pid ? 'border-accent bg-accent/10 text-accent' : 'border-line text-muted hover:text-ink'}`}>
            {cleared.includes(p.id) && <span className="text-good" aria-label="cleared">✓ </span>}{p.title}
          </button>
        ))}
      </div>
      {problem && <RichText text={problem.prompt} className="mb-3 text-sm" />}
      <CodeEditor value={code} onChange={setCode} height={220} onSubmit={answer !== null ? submit : undefined} />

      {q && (
        <div className="mt-5 rounded-lg border border-line bg-raised p-4">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Concept question</h4>
            {info.concept_questions.length > 1 && (
              <button type="button" className="min-h-[44px] text-sm text-accent hover:underline" onClick={() => { setQi((qi + 1) % info.concept_questions.length); setAnswer(null) }}>another question</button>
            )}
          </div>
          <pre className="mb-3 whitespace-pre-wrap font-mono text-[15px]">{q.q}</pre>
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Concept question answers">
            {q.options.map((o, i) => (
              <button key={i} role="radio" aria-checked={answer === i} onClick={() => setAnswer(i)}
                className={`min-h-[44px] rounded-lg border px-3 py-2 text-left font-mono text-sm transition ${answer === i ? 'border-accent bg-accent/10' : 'border-line hover:border-accent/60'}`}>{o}</button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="text-xs text-muted">{answer === null ? 'Answer the concept question to submit.' : 'Ctrl/⌘ + Enter in the editor also submits.'}</span>
        <Button disabled={busy || answer === null || !pid} onClick={submit}>{busy ? 'Checking…' : 'Check my answer'}</Button>
      </div>
      <div className="mt-3"><ErrorNote error={error} /></div>
      {advanced && <p className="mt-4 rounded-lg border border-good/40 bg-good/10 p-3 text-sm text-good" role="status">{advanced}</p>}
      {result && <div className="mt-4"><Result r={result} fn={fnOf(info, result)} /></div>}
      {result?.mastery_after != null && <div className="mt-4"><Bar value={result.mastery_after} tone={result.resolved ? 'good' : 'warn'} label="Mastery of this idea" right={`${Math.round(result.mastery_after * 100)}%`} /></div>}
    </Card>
  )
}
