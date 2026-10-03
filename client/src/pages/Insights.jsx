import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { API, api } from '../api'
import { Card, CodeView, ErrorNote, Pill } from '../components/ui'

const pct = (x) => `${Math.round(x * 100)}%`

function ShareBar({ share, tone = 'bg-bad' }) {
  return (
    <div className="h-3 w-full overflow-hidden rounded-full bg-raised" role="img" aria-label={`${pct(share)} of wrong attempts`}>
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(2, share * 100)}%` }} />
    </div>
  )
}

function Group({ title, sub, g, tone }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold">{title}</p>
        <p className="text-sm text-muted tabular-nums">
          {g.count} attempt{g.count === 1 ? '' : 's'} · {pct(g.share)} · {g.unique_learners} learner{g.unique_learners === 1 ? '' : 's'}
          {g.synthetic > 0 && <> · <Pill tone="warn">{g.synthetic} synthetic</Pill></>}
        </p>
      </div>
      <div className="mt-2"><ShareBar share={g.share} tone={tone} /></div>
      {sub && <p className="mt-2 text-sm text-ink/90">{sub}</p>}
      {g.typical_failing_test && <p className="mt-1 text-sm text-muted">{g.typical_failing_test.words}</p>}
      <p className="mt-1 text-xs text-muted">Problems: {Object.entries(g.problems).map(([p, n]) => `${p} (${n})`).join(', ')}</p>
      {g.examples.length > 0 && (
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
          className="mt-3 min-h-[44px] text-sm font-medium text-accent hover:underline">
          {open ? 'Hide examples' : `Show ${g.examples.length} example${g.examples.length === 1 ? '' : 's'}`}
        </button>
      )}
      {open && (
        <div className="mt-2 grid gap-3 md:grid-cols-2">
          {g.examples.map((e, i) => (
            <CodeView key={i} code={e.code} highlight={e.highlight_lines} label={`${e.problem_id} · learner ${e.learner}${e.synthetic ? ' (synthetic)' : ''}`}
              caption={e.highlight_lines.length ? 'Highlighted: the line(s) a verified fix changes.' : undefined} />
          ))}
        </div>
      )}
    </li>
  )
}

export default function Insights() {
  const [synthetic, setSynthetic] = useState(false)
  const [withCode, setWithCode] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    api.insights(synthetic).then((d) => live && setData(d)).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [synthetic])

  const csv = `${API}/insights/export.csv?include_code=${withCode}&include_synthetic=${synthetic}`
  return (
    <div className="space-y-6">
      <Card title="Common mistakes" right={<Link to="/dashboard" className="text-sm text-accent hover:underline">← Dashboard</Link>}>
        <p className="text-sm text-muted">
          What learners actually get wrong, from every submission that failed. Learners are counted by an anonymous code (a salted hash), never by name.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
          <label className="flex min-h-[44px] items-center gap-2">
            <input type="checkbox" checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} className="h-5 w-5" />
            Include <Pill tone="warn">SYNTHETIC</Pill> demo data
          </label>
          <label className="flex min-h-[44px] items-center gap-2">
            <input type="checkbox" checked={withCode} onChange={(e) => setWithCode(e.target.checked)} className="h-5 w-5" />
            Include code in the CSV
          </label>
          <a href={csv} className="inline-flex min-h-[44px] items-center rounded-lg border border-line px-4 font-semibold hover:bg-raised" download>
            Export CSV
          </a>
        </div>
      </Card>

      <ErrorNote error={error} />
      {!data && !error && <p className="text-sm text-muted">Loading…</p>}
      {data && data.total_wrong_attempts === 0 && (
        <Card title="Nothing yet"><p className="text-sm text-muted">No wrong submissions recorded{synthetic ? '' : ' (tick SYNTHETIC to see demo data)'}.</p></Card>
      )}
      {data && data.total_wrong_attempts > 0 && (
        <>
          <Card title={`Named mistakes · ${data.total_wrong_attempts} wrong attempts · ${data.unique_learners} learners`}>
            {data.mistakes.length === 0 ? <p className="text-sm text-muted">None of the 8 common mistakes yet.</p> : (
              <ul className="space-y-3">
                {data.mistakes.map((g) => <Group key={g.label} g={g} title={`${g.name}`} sub={g.lesson_summary} />)}
              </ul>
            )}
          </Card>
          <Card title="Bugs the model could not name" right={<Pill tone="warn">grouped by failing tests</Pill>}>
            {data.unknown_clusters.length === 0 ? <p className="text-sm text-muted">None.</p> : (
              <ul className="space-y-3">
                {data.unknown_clusters.map((g, i) => (
                  <Group key={i} g={g} tone="bg-warn" title={`${g.signature.problem_id}: ${g.signature_words}`} />
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
