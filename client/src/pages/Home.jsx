import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, learnerId } from '../api'
import CodeEditor from '../components/CodeEditor'
import DiagnosisCard from '../components/DiagnosisCard'
import ExplainPanel from '../components/ExplainPanel'
import HintPanel, { MAX_HINTS } from '../components/HintPanel'
import InterventionPanel from '../components/InterventionPanel'
import TransferPanel from '../components/TransferPanel'
import { useServerHealth } from '../serverHealth'
import { Button, Card, ErrorNote, Pill, RichText } from '../components/ui'
import { DEMOS } from '../labels'

export default function Home() {
  const [lid] = useState(learnerId)
  const { healthy } = useServerHealth()
  const [params] = useSearchParams()
  const showDemo = params.get('demo') === '1' // demo-bug panel is hidden unless the URL has ?demo=1
  const [problems, setProblems] = useState([])
  const [pid, setPid] = useState('sum_list')
  const [code, setCode] = useState('')
  const [diag, setDiag] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [proving, setProving] = useState(false)
  const [submitted, setSubmitted] = useState(null) // the exact problem + code that was diagnosed (the editor may change afterwards)
  const [demo, setDemo] = useState(null)
  const [hints, setHints] = useState([]) // revealed hints, one per level (max 3)
  const [hintBusy, setHintBusy] = useState(false)
  const [hintError, setHintError] = useState('')
  const [hintNote, setHintNote] = useState('')
  const pidRef = useRef(pid)
  const diagRef = useRef(null)
  const proveRef = useRef(null)

  useEffect(() => {
    if (!healthy) return // wait until the server is awake
    api.problems()
      .then((ps) => { setProblems(ps); const p = ps.find((x) => x.id === params.get('problem')) || ps.find((x) => x.id === 'sum_list') || ps[0]; setPid(p.id); setCode(p.starter) })
      .catch((e) => setError(e.message))
  }, [healthy]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { pidRef.current = pid }, [pid])

  const problem = problems.find((p) => p.id === pid)
  const resetHints = () => { setHints([]); setHintError(''); setHintNote('') }
  const reset = () => { setDiag(null); setProving(false); setError('') }

  const pick = (id) => {
    const p = problems.find((x) => x.id === id)
    setPid(id); setCode(p.starter); setDemo(null); reset(); resetHints()
  }
  const loadDemo = (d) => { setPid(d.problem); setCode(d.code); setDemo(d); reset(); resetHints() }

  const askHint = async () => {
    if (hintBusy || hints.length >= MAX_HINTS || !problem) return
    const forPid = pid
    setHintBusy(true); setHintError(''); setHintNote('')
    try {
      const res = await api.hint({
        problem_id: pid, problem_statement: problem.prompt, code, hint_level: hints.length + 1, learner_id: lid,
        test_results: (diag?.test_results ?? []).map(({ args, expected, got, ok, error }) => ({ args, expected, got, ok, error })), // last results, if any
      })
      if (pidRef.current !== forPid) return // the problem changed while we were waiting
      if (res.source === 'none') setHintNote(res.hint) // all tests pass: nothing to reveal, no level used
      else setHints((h) => [...h, res])
    } catch (e) {
      if (pidRef.current === forPid) setHintError(e.message)
    } finally {
      setHintBusy(false)
    }
  }

  const submit = async () => {
    setBusy(true); setError(''); setProving(false)
    try {
      const d = await api.diagnose({ problem_id: pid, code, learner_id: lid })
      setSubmitted({ pid, code, n: Date.now() })
      setDiag(d)
      setTimeout(() => diagRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const prove = () => {
    setProving(true)
    setTimeout(() => proveRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  // only a confident misconception gets a lesson; an unknown bug gets a step-by-step explanation instead
  const misconception = diag?.verdict ? (diag.verdict === 'misconception' ? diag.label : null) : (diag?.label && diag.label !== 'CORRECT' ? diag.label : null)
  const unknownBug = diag?.verdict === 'unknown' && diag?.status === 'ok' && diag?.label

  return (
    <div className="space-y-6">
      <Card title="1 · Pick a problem and write your solution">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label htmlFor="problem" className="text-sm text-muted">Problem</label>
          <select id="problem" value={pid} onChange={(e) => pick(e.target.value)}
            className="rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink">
            {problems.map((p) => <option key={p.id} value={p.id}>{p.title}{p.custom ? ' (custom)' : ''}</option>)}
          </select>
          {problem?.badge && <Pill tone="info">{problem.badge}</Pill>}
        </div>
        {problem && (
          <div className="mb-4">
            <RichText text={problem.prompt} className="text-sm" />
            <p className="mt-1 font-mono text-xs text-muted">
              e.g. {problem.function}({problem.example.args.map((a) => JSON.stringify(a)).join(', ')}) → {JSON.stringify(problem.example.expected)}
            </p>
          </div>
        )}

        {showDemo && (
        <div className="mb-4 rounded-lg border border-line bg-raised p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Load demo bug (twin pairs - look alike, different cause)</p>
          <div className="flex flex-wrap gap-2">
            {DEMOS.map((d) => (
              <button key={d.id} onClick={() => loadDemo(d)} title={d.blurb}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${demo?.id === d.id ? 'border-accent bg-accent/10 text-accent' : 'border-line text-ink hover:border-accent/60'}`}>
                {d.id} <span className="text-muted">({d.pair})</span>
              </button>
            ))}
          </div>
          {demo && <p className="mt-2 text-xs text-muted">Loaded {demo.id}: {demo.blurb}</p>}
        </div>
        )}

        <CodeEditor value={code} onChange={setCode} onSubmit={submit} />
        <div className="mt-4 flex items-center justify-between gap-3">
          <span className="text-xs text-muted">Ctrl/⌘ + Enter submits · learner <code className="font-mono">{lid}</code></span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={askHint} disabled={!healthy || hintBusy || hints.length >= MAX_HINTS || !pid}>
              {hintBusy ? 'Thinking…' : hints.length >= MAX_HINTS ? 'No more hints' : hints.length === 0 ? 'Hint' : 'Next hint'}
            </Button>
            <Button onClick={submit} disabled={!healthy || busy || !pid}>{!healthy ? 'Waiting for server…' : busy ? 'Running…' : 'Submit'}</Button>
          </div>
        </div>
        <HintPanel hints={hints} loading={hintBusy} note={hintNote} error={hintError} />
        <div className="mt-3"><ErrorNote error={error} /></div>
      </Card>

      {diag && (
        <div ref={diagRef} className="scroll-mt-20 space-y-6">
          <DiagnosisCard diag={diag} />
          {diag.label === 'CORRECT' && (
            <Card><p className="text-sm text-good">Nice - no misconception detected.{showDemo && ' Try a demo bug above to see the diagnosis → intervention → proof loop.'}</p></Card>
          )}
          {(unknownBug || misconception) && <ExplainPanel key={`explain:${submitted?.n}`} label={misconception} problemId={submitted?.pid ?? pid} code={submitted?.code ?? code} />}
          {misconception && <InterventionPanel key={`${misconception}:${submitted?.n}`} explained label={misconception} problemId={submitted?.pid ?? pid} code={submitted?.code ?? code} learnerId={lid} onProve={prove} />}
        </div>
      )}

      {misconception && proving && (
        <div ref={proveRef} className="scroll-mt-20">
          <TransferPanel key={`${misconception}:${submitted?.n}`} label={misconception} learnerId={lid} originalProblemId={submitted?.pid ?? pid} />
        </div>
      )}
      {!problems.length && !error && <Pill>Loading problems…</Pill>}
    </div>
  )
}
