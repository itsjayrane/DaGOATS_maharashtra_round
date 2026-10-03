import { useState } from 'react'
import { api } from '../api'
import { Button, Card, CodeView, ErrorNote, Pill } from './ui'
import { py } from '../labels'

const MIN = 10

// "Practise your own question": an AI only drafts the problem; the server runs the drafted solution to get the
// expected answers, and checking the learner's code uses the usual offline tests, diagnosis and hints.
export function OwnQuestionCard({ learnerId, healthy, onCreated }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [made, setMade] = useState(null)
  const ok = text.trim().length >= MIN

  const create = async () => {
    setBusy(true); setError(''); setMade(null)
    try {
      const p = await api.practiceOwn(text.trim(), learnerId)
      setMade(p)
      onCreated(p)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <Card title="Practise your own question" right={<Pill tone="info">AI-drafted, checked by running</Pill>}>
      <label htmlFor="own-q" className="mb-2 block text-sm text-ink/90">
        Type any beginner Python question. We turn it into a problem with tests, then check your answer the usual way.
      </label>
      <textarea id="own-q" value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={2000}
        placeholder="e.g. Write a function that returns the second largest number in a list"
        className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink" />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-muted">{text.trim().length < MIN ? `At least ${MIN} characters.` : `${text.length} / 2000`}</span>
        <Button onClick={create} disabled={!healthy || busy || !ok}>{busy ? 'Working…' : 'Create my problem'}</Button>
      </div>
      {busy && <p className="mt-3 text-sm text-muted" role="status">Writing and checking your problem… (up to 20 s)</p>}
      <div className="mt-3"><ErrorNote error={error} /></div>
      {made && (
        <div className="mt-3 rounded-lg border border-good/40 bg-good/10 p-3 text-sm" data-testid="own-made" role="status">
          <p className="font-semibold text-good">Your problem is ready below - write the function {made.function}.</p>
          <p className="mt-1 font-mono">Example: {made.function}({made.example.args.map(py).join(', ')}) → {py(made.example.expected)}</p>
          {made.assumptions && made.assumptions !== 'none' && <p className="mt-1 text-ink/90">How we read your question: {made.assumptions}</p>}
        </div>
      )}
    </Card>
  )
}

// Reveal the verified solution of an AI-drafted problem: on request (after offering a hint first) or after passing.
export function SolutionReveal({ problem, learnerId, passed, onHint }) {
  const [stage, setStage] = useState('hidden') // hidden -> ask -> shown
  const [sol, setSol] = useState(null)
  const [error, setError] = useState('')
  const load = async () => {
    setError('')
    try { setSol(await api.getSolution(problem.id, learnerId)); setStage('shown') } catch (e) { setError(e.message) }
  }
  if (problem?.source !== 'ai_draft') return null
  if (stage === 'shown' && sol) {
    return (
      <div className="mt-4" data-testid="solution">
        <CodeView code={sol.reference_solution} tone="good" label={passed ? 'Compare with our solution' : 'Our solution'} caption={sol.note} />
      </div>
    )
  }
  if (passed) {
    return (
      <div className="mt-4">
        <Button variant="ghost" onClick={load}>Compare with our solution</Button>
        <ErrorNote error={error} />
      </div>
    )
  }
  return (
    <div className="mt-4">
      {stage === 'hidden' && <Button variant="ghost" onClick={() => setStage('ask')}>Show solution</Button>}
      {stage === 'ask' && (
        <div className="rounded-lg border border-line bg-raised p-3" role="group" aria-label="Show the solution?">
          <p className="text-sm">Try a hint first? Working it out yourself helps it stick.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button onClick={() => { setStage('hidden'); onHint() }}>Get a hint</Button>
            <Button variant="ghost" onClick={load}>Show it anyway</Button>
          </div>
        </div>
      )}
      <div className="mt-2"><ErrorNote error={error} /></div>
    </div>
  )
}
