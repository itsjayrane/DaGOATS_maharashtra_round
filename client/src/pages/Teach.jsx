import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Button, Card, ErrorNote, Pill } from '../components/ui'
import { pyToJson, toPy } from '../pylit'
import { useServerHealth } from '../serverHealth'

function parseInputs(text) {
  return JSON.parse(`[${pyToJson(text)}]`) // "'banana'" -> ["banana"];  "[1, 2], 3" -> [[1, 2], 3]
}

const EMPTY = { input: '', expected: '' }
const field = 'w-full rounded-lg border border-line bg-raised px-3 py-2 text-ink'

export default function Teach() {
  const [statement, setStatement] = useState('')
  const [fn, setFn] = useState('')
  const [ref, setRef] = useState('')
  const [tests, setTests] = useState([{ ...EMPTY }, { ...EMPTY }, { ...EMPTY }, { ...EMPTY }])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [made, setMade] = useState(null)
  const { healthy } = useServerHealth()
  const [draftOn, setDraftOn] = useState(false) // optional AI drafting configured on the server
  const [question, setQuestion] = useState('')
  const [drafting, setDrafting] = useState(false)
  const [draftError, setDraftError] = useState('')
  const [drafted, setDrafted] = useState(null) // the draft currently loaded into the form (source: ai_draft)

  useEffect(() => {
    if (!healthy) return
    api.draftStatus().then((st) => setDraftOn(!!st.available)).catch(() => setDraftOn(false))
  }, [healthy])

  const draftIt = async () => {
    setDrafting(true); setDraftError(''); setMade(null); setError('')
    try {
      const d = await api.draftCustom(question.trim())
      setStatement(d.statement); setFn(d.function_name); setRef(d.reference_solution)
      setTests(d.tests.map((t) => ({ input: t.input.map(toPy).join(', '), expected: toPy(t.expected) })))
      setDrafted(d)
    } catch (e) { setDraftError(e.message) } finally { setDrafting(false) }
  }

  const setTest = (i, key, v) => setTests((ts) => ts.map((t, j) => (j === i ? { ...t, [key]: v } : t)))

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setMade(null)
    let body
    try {
      body = {
        statement, function_name: fn.trim(), reference_solution: ref, source: drafted ? 'ai_draft' : 'teacher',
        tests: tests.filter((t) => t.input.trim()).map((t, i) => {
          try {
            const out = { input: parseInputs(t.input) }
            if (t.expected.trim()) out.expected = JSON.parse(pyToJson(t.expected))
            return out
          } catch {
            throw new Error(`Test ${i + 1}: could not read the values. Write them like Python, e.g. 'banana' or [1, 2], 3`)
          }
        }),
      }
    } catch (err) { setError(err.message); return }
    setBusy(true)
    try { setMade(await api.createCustom(body)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-6">
      {draftOn && (
        <Card title="Just type your question" right={<Pill tone="info">AI drafts, you review</Pill>}>
          <label htmlFor="teach-q" className="mb-2 block text-sm text-ink/90">
            Describe the exercise in plain words. An AI drafts the function, a solution and test inputs; we run the solution to get
            the expected answers and fill in the form below for you to check and edit before saving.
          </label>
          <textarea id="teach-q" value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} maxLength={2000} className={field}
            placeholder="e.g. Return the second largest distinct number in a list, or None if there isn't one" />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-muted">{drafting ? 'Writing and checking a draft… (up to 25 s)' : 'At least 10 characters.'}</span>
            <Button type="button" onClick={draftIt} disabled={!healthy || drafting || question.trim().length < 10}>{drafting ? 'Drafting…' : 'Draft it for me'}</Button>
          </div>
          <div className="mt-3"><ErrorNote error={draftError} /></div>
          {drafted && (
            <p className="mt-3 text-sm text-good" role="status">
              Draft loaded below ({drafted.tests.length} tests, answers from running the solution). How it was read: {drafted.assumptions}
            </p>
          )}
        </Card>
      )}

      <Card title="Add your own problem" right={<Pill tone="info">for teachers</Pill>}>
        <p className="mb-4 text-sm text-muted">
          Write the task, a correct solution and at least 4 tests. We run your solution to check it and to fill in any expected
          answers you leave empty. Learners then get the same feedback as on the built-in problems (no AI is used anywhere).
        </p>
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Problem statement</span>
            <textarea required value={statement} onChange={(e) => setStatement(e.target.value)} rows={3} className={field}
              placeholder="Count how many lowercase vowels (a, e, i, o, u) are in the word." />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Function name</span>
            <input required value={fn} onChange={(e) => setFn(e.target.value)} className={`${field} font-mono`} placeholder="count_vowels" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Correct (reference) solution</span>
            <textarea required value={ref} onChange={(e) => setRef(e.target.value)} rows={7} spellCheck={false} className={`${field} font-mono text-[15px]`}
              placeholder={'def count_vowels(word):\n    n = 0\n    for ch in word:\n        if ch in "aeiou":\n            n += 1\n    return n'} />
          </label>
          <fieldset>
            <legend className="mb-1 text-sm font-medium">Tests (at least 4)</legend>
            <p className="mb-2 text-xs text-muted">Inputs are the function&apos;s arguments, written like Python and separated by commas. Leave &quot;expected&quot; empty to use your solution&apos;s answer.</p>
            <div className="space-y-2">
              {tests.map((t, i) => (
                <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                  <input aria-label={`Test ${i + 1} inputs`} value={t.input} onChange={(e) => setTest(i, 'input', e.target.value)} className={`${field} font-mono`} placeholder={i === 0 ? "'banana'" : 'inputs'} />
                  <input aria-label={`Test ${i + 1} expected (optional)`} value={t.expected} onChange={(e) => setTest(i, 'expected', e.target.value)} className={`${field} font-mono`} placeholder="expected (optional)" />
                  <Button type="button" variant="ghost" aria-label={`Remove test ${i + 1}`} onClick={() => setTests((ts) => ts.filter((_, j) => j !== i))} disabled={tests.length <= 1}>Remove</Button>
                </div>
              ))}
            </div>
            <Button type="button" variant="ghost" className="mt-2" onClick={() => setTests((ts) => [...ts, { ...EMPTY }])}>Add a test</Button>
          </fieldset>
          <ErrorNote error={error} />
          <Button type="submit" disabled={busy}>{busy ? 'Checking your solution…' : 'Create problem'}</Button>
        </form>
      </Card>

      {made && (
        <Card title="Problem created" right={<Pill tone="good">{made.badge}</Pill>}>
          <p className="text-sm">&quot;{made.title}&quot; is ready. Your solution passed every test; expected answers were filled in where you left them empty:</p>
          <ul className="mt-2 space-y-1 font-mono text-sm">
            {made.tests.map((t, i) => <li key={i}>{made.function}({t.input.map((a) => JSON.stringify(a)).join(', ')}) → {JSON.stringify(t.expected)}</li>)}
          </ul>
          <Link to={`/?problem=${made.id}`} className="mt-4 inline-block text-accent hover:underline">Practise it now →</Link>
        </Card>
      )}
    </div>
  )
}
