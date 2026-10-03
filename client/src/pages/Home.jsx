import { useEffect, useRef, useState } from 'react'
import { api, learnerId } from '../api'
import CodeEditor from '../components/CodeEditor'
import DiagnosisCard from '../components/DiagnosisCard'
import InterventionPanel from '../components/InterventionPanel'
import TransferPanel from '../components/TransferPanel'
import { Button, Card, ErrorNote, Pill, RichText } from '../components/ui'
import { DEMOS } from '../labels'

export default function Home() {
  const [lid] = useState(learnerId)
  const [problems, setProblems] = useState([])
  const [pid, setPid] = useState('sum_list')
  const [code, setCode] = useState('')
  const [diag, setDiag] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [proving, setProving] = useState(false)
  const [demo, setDemo] = useState(null)
  const diagRef = useRef(null)
  const proveRef = useRef(null)

  useEffect(() => {
    api.problems()
      .then((ps) => { setProblems(ps); const p = ps.find((x) => x.id === 'sum_list') || ps[0]; setPid(p.id); setCode(p.starter) })
      .catch((e) => setError(e.message))
  }, [])

  const problem = problems.find((p) => p.id === pid)
  const reset = () => { setDiag(null); setProving(false); setError('') }

  const pick = (id) => {
    const p = problems.find((x) => x.id === id)
    setPid(id); setCode(p.starter); setDemo(null); reset()
  }
  const loadDemo = (d) => { setPid(d.problem); setCode(d.code); setDemo(d); reset() }

  const submit = async () => {
    setBusy(true); setError(''); setProving(false)
    try {
      const d = await api.diagnose({ problem_id: pid, code, learner_id: lid })
      setDiag(d)
      setTimeout(() => diagRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const prove = () => {
    setProving(true)
    setTimeout(() => proveRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  const misconception = diag?.label && diag.label !== 'CORRECT' ? diag.label : null

  return (
    <div className="space-y-6">
      <Card title="1 · Pick a problem and write your solution">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label htmlFor="problem" className="text-sm text-muted">Problem</label>
          <select id="problem" value={pid} onChange={(e) => pick(e.target.value)}
            className="rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink">
            {problems.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
        </div>
        {problem && (
          <div className="mb-4">
            <RichText text={problem.prompt} className="text-sm" />
            <p className="mt-1 font-mono text-xs text-muted">
              e.g. {problem.function}({problem.example.args.map((a) => JSON.stringify(a)).join(', ')}) → {JSON.stringify(problem.example.expected)}
            </p>
          </div>
        )}

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

        <CodeEditor value={code} onChange={setCode} onSubmit={submit} />
        <div className="mt-4 flex items-center justify-between gap-3">
          <span className="text-xs text-muted">Ctrl/⌘ + Enter submits · learner <code className="font-mono">{lid}</code></span>
          <Button onClick={submit} disabled={busy || !pid}>{busy ? 'Running…' : 'Submit'}</Button>
        </div>
        <div className="mt-3"><ErrorNote error={error} /></div>
      </Card>

      {diag && (
        <div ref={diagRef} className="scroll-mt-20 space-y-6">
          <DiagnosisCard diag={diag} />
          {diag.label === 'CORRECT' && (
            <Card><p className="text-sm text-good">Nice - no misconception detected. Try a demo bug above to see the diagnosis → intervention → proof loop.</p></Card>
          )}
          {misconception && <InterventionPanel key={`${misconception}:${pid}`} label={misconception} onProve={prove} />}
        </div>
      )}

      {misconception && proving && (
        <div ref={proveRef} className="scroll-mt-20">
          <TransferPanel key={`${misconception}:${pid}`} label={misconception} learnerId={lid} originalProblemId={pid} />
        </div>
      )}
      {!problems.length && !error && <Pill>Loading problems…</Pill>}
    </div>
  )
}
