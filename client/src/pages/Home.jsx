import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, learnerId } from '../api'
import CodeEditor from '../components/CodeEditor'
import DiagnosisCard from '../components/DiagnosisCard'
import ExplainPanel from '../components/ExplainPanel'
import HintPanel, { MAX_HINTS } from '../components/HintPanel'
import InterventionPanel from '../components/InterventionPanel'
import Onboarding from '../components/Onboarding'
import QuickCheck from '../components/QuickCheck'
import StepIndicator from '../components/StepIndicator'
import TransferPanel from '../components/TransferPanel'
import { useServerHealth } from '../serverHealth'
import { flag, setFlag } from '../theme'
import { Button, Card, ErrorNote, Pill, RichText } from '../components/ui'
import { byDifficulty, DEMOS, DIFFICULTY, py, TWIN_OF } from '../labels'

const TWIN_PROBE_MIN = 0.2 // ask the twin probe when the look-alike mistake has at least this probability

function DifficultyPill({ p }) {
  if (p?.custom) return <Pill tone="info">{p.badge}</Pill>
  const d = DIFFICULTY[p?.difficulty]
  return d ? <Pill tone={d[1]}>{d[0]}</Pill> : null
}

export default function Home() {
  const [lid] = useState(learnerId)
  const { healthy } = useServerHealth()
  const [params] = useSearchParams()
  const showDemo = params.get('demo') === '1' // demo-bug panel is hidden unless the URL has ?demo=1
  const [onboard, setOnboard] = useState(() => !flag('onboarded'))
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
  const [solved, setSolved] = useState([])
  const [suggested, setSuggested] = useState(null) // from GET /learner/{id}/patterns
  const [override, setOverride] = useState(null) // twin chosen by the Quick check answer
  const pidRef = useRef(pid)
  const diagRef = useRef(null)
  const proveRef = useRef(null)

  useEffect(() => {
    if (!healthy) return // wait until the server is awake
    api.problems()
      .then((raw) => {
        const ps = [...raw].sort(byDifficulty) // easy problems first
        setProblems(ps)
        const p = ps.find((x) => x.id === params.get('problem')) || ps[0]
        setPid(p.id); setCode(p.starter)
      })
      .catch((e) => setError(e.message))
  }, [healthy]) // eslint-disable-line react-hooks/exhaustive-deps

  // what this learner already solved + the problem the pattern analysis suggests; refreshed after every check
  useEffect(() => {
    if (!healthy) return
    api.learner(lid).then((d) => setSolved([...new Set(d.history.filter((h) => h.passed).map((h) => h.problem_id))])).catch(() => setSolved([]))
    api.patterns(lid).then((d) => setSuggested(d.suggested_next)).catch(() => setSuggested(null))
  }, [healthy, lid, diag])

  useEffect(() => { pidRef.current = pid }, [pid])

  const problem = problems.find((p) => p.id === pid)
  const recommended = problems.find((p) => p.id === suggested?.problem_id && p.id !== pid)
    || problems.find((p) => !solved.includes(p.id) && p.id !== pid && !p.custom)
  const resetHints = () => { setHints([]); setHintError(''); setHintNote('') }
  const reset = () => { setDiag(null); setProving(false); setError(''); setOverride(null) }

  const pick = (id) => {
    const p = problems.find((x) => x.id === id)
    setPid(id); setCode(p.starter); setDemo(null); reset(); resetHints()
  }
  const loadDemo = (d) => { setPid(d.problem); setCode(d.code); setDemo(d); reset(); resetHints() }
  const finishOnboarding = () => { setFlag('onboarded'); setOnboard(false) }

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
    setBusy(true); setError(''); setProving(false); setOverride(null)
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
  const diagnosed = diag?.verdict ? (diag.verdict === 'misconception' ? diag.label : null) : (diag?.label && diag.label !== 'CORRECT' ? diag.label : null)
  const misconception = override || diagnosed
  // two look-alike mistakes are close: ask one twin probe question before teaching
  const twinClose = diagnosed && diag.runner_up && TWIN_OF[diagnosed] === diag.runner_up.label && (diag.ambiguous || diag.runner_up.probability >= TWIN_PROBE_MIN)
  const unknownBug = diag?.verdict === 'unknown' && diag?.status === 'ok' && diag?.label
  const correct = diag && (diag.verdict ? diag.verdict === 'correct' : diag.label === 'CORRECT')
  const step = proving ? 3 : misconception || unknownBug ? 2 : diag ? 1 : 0

  return (
    <div className="space-y-6">
      {onboard && <Onboarding onDone={finishOnboarding} />}
      <StepIndicator current={step} allDone={correct} />

      <Card title="Write your solution" right={!onboard && (
        <button type="button" onClick={() => setOnboard(true)} className="min-h-[44px] text-sm text-accent hover:underline">How it works</button>
      )}>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <label htmlFor="problem" className="text-sm text-muted">Problem</label>
          <select id="problem" value={pid} onChange={(e) => pick(e.target.value)}
            className="min-h-[44px] max-w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink">
            {problems.map((p) => (
              <option key={p.id} value={p.id}>
                {solved.includes(p.id) ? '✓ ' : ''}{p.title} · {p.custom ? 'custom' : DIFFICULTY[p.difficulty]?.[0] ?? ''}{p.id === recommended?.id ? ' · recommended' : ''}
              </option>
            ))}
          </select>
          <DifficultyPill p={problem} />
          {solved.includes(pid) && <Pill tone="good">solved before</Pill>}
        </div>
        {problem && (
          <div className="mb-4">
            {problem.framing && <p className="mb-2 text-sm italic text-muted" data-testid="framing">In real life: {problem.framing}</p>}
            <RichText text={problem.prompt} className="text-sm" />
            <p className="mt-1 font-mono text-sm text-muted">
              Example: {problem.function}({problem.example.args.map(py).join(', ')}) → {py(problem.example.expected)}
            </p>
          </div>
        )}

        {showDemo && (
        <div className="mb-4 rounded-lg border border-line bg-raised p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Load demo bug (twin pairs - look alike, different cause)</p>
          <div className="flex flex-wrap gap-2">
            {DEMOS.map((d) => (
              <button key={d.id} onClick={() => loadDemo(d)} title={d.blurb}
                className={`min-h-[44px] rounded-lg border px-3 py-1.5 text-xs font-medium transition ${demo?.id === d.id ? 'border-accent bg-accent/10 text-accent' : 'border-line text-ink hover:border-accent/60'}`}>
                {d.id} <span className="text-muted">({d.pair})</span>
              </button>
            ))}
          </div>
          {demo && <p className="mt-2 text-xs text-muted">Loaded {demo.id}: {demo.blurb}</p>}
        </div>
        )}

        <CodeEditor value={code} onChange={setCode} onSubmit={submit} />
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-muted">Tip: Ctrl + Enter also checks your code.</span>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={askHint} disabled={!healthy || hintBusy || hints.length >= MAX_HINTS || !pid}>
              {hintBusy ? 'Thinking…' : hints.length >= MAX_HINTS ? 'No more hints' : hints.length === 0 ? 'Get a hint' : 'Next hint'}
            </Button>
            <Button onClick={submit} disabled={!healthy || busy || !pid}>{!healthy ? 'Waiting for server…' : busy ? 'Checking…' : 'Check my code'}</Button>
          </div>
        </div>
        <HintPanel hints={hints} loading={hintBusy} note={hintNote} error={hintError} />
        <div className="mt-3"><ErrorNote error={error} /></div>
      </Card>

      {diag && (
        <div ref={diagRef} className="scroll-mt-20 space-y-6">
          <DiagnosisCard diag={diag} fn={problems.find((p) => p.id === submitted?.pid)?.function ?? problem?.function} />
          {twinClose && <QuickCheck key={`probe:${submitted?.n}`} a={diagnosed} b={diag.runner_up.label} current={diagnosed} learnerId={lid} problemId={submitted?.pid ?? pid} onPick={setOverride} />}
          {(unknownBug || misconception) && <ExplainPanel key={`explain:${misconception}:${submitted?.n}`} label={misconception} problemId={submitted?.pid ?? pid} code={submitted?.code ?? code} />}
          {misconception && <InterventionPanel key={`${misconception}:${submitted?.n}`} explained label={misconception} problemId={submitted?.pid ?? pid} code={submitted?.code ?? code} learnerId={lid} onProve={prove} />}
        </div>
      )}

      {misconception && proving && (
        <div ref={proveRef} className="scroll-mt-20">
          <TransferPanel key={`${misconception}:${submitted?.n}`} label={misconception} learnerId={lid} originalProblemId={submitted?.pid ?? pid} />
        </div>
      )}

      {recommended && (
        <Card title="Recommended next" right={<DifficultyPill p={recommended} />}>
          <div className="flex flex-wrap items-center justify-between gap-3" data-testid="recommended">
            <div className="min-w-0">
              <p className="font-semibold">{recommended.title}</p>
              <p className="text-sm text-muted">
                {suggested?.problem_id === recommended.id ? suggested.reason : recommended.framing || 'The next problem you have not solved yet.'}
              </p>
            </div>
            <Button variant="ghost" onClick={() => { pick(recommended.id); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>Start this one</Button>
          </div>
        </Card>
      )}
      {!problems.length && !error && <Pill>Loading problems…</Pill>}
    </div>
  )
}
