import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, learnerId } from '../api'
import { Bar, Card, ErrorNote, Pill } from '../components/ui'
import { MISC, short } from '../labels'

const HINT = "Drops when we spot this mistake in your code. Rises when you prove you've fixed it on a new problem."
const TOP_N = 2

const pct = (m) => Math.round(m * 100)
// red < 40%, yellow 40-70%, green > 70% (judged on the number shown, so "70%" is never green)
const tone = (m) => (pct(m) > 70 ? 'good' : pct(m) >= 40 ? 'warn' : 'bad')

// One row per misconception, with how much evidence we have for it.
function summarise(data) {
  return MISC.map(([full, id, name]) => {
    const rows = data.history.filter((h) => h.misconception === full)
    const m = data.mastery[full] || { mastery: 0.5, resolved: false }
    const detected = rows.filter((h) => h.kind === 'diagnose') // "detected" = a submission diagnosed as this
    const last = Math.max(0, ...(detected.length ? detected : rows).map((h) => h.ts))
    return { full, id, name, attempts: rows.length, mastery: m.mastery, resolved: m.resolved, last }
  })
}

function InfoTip({ text }) {
  const tipId = useId()
  return (
    <span className="group relative ml-2 inline-flex align-middle">
      <button type="button" aria-label="What does mastery mean?" aria-describedby={tipId}
        className="flex h-4 w-4 items-center justify-center rounded-full border border-muted text-[10px] font-semibold normal-case text-muted hover:text-ink focus:text-ink">i</button>
      <span id={tipId} role="tooltip"
        className="pointer-events-none absolute left-0 top-6 z-20 hidden w-64 rounded-lg border border-line bg-raised p-3 text-xs font-normal normal-case leading-relaxed tracking-normal text-ink shadow-lg group-focus-within:block group-hover:block">
        {text}
      </span>
    </span>
  )
}

function EmptyProgress() {
  return (
    <p className="text-sm text-muted" data-testid="mastery-empty">
      Submit a solution on the <Link to="/" className="text-accent hover:underline">Practice page</Link> to see your progress.
    </p>
  )
}

function MasteryRow({ r }) {
  if (r.attempts === 0) {
    return (
      <div className="flex items-center justify-between gap-3 text-xs" data-testid="mastery-row" data-seen="false">
        <span className="text-ink">{r.id} · {r.name}</span>
        <span className="rounded-full border border-line bg-raised px-2 py-0.5 text-muted">Not seen yet</span>
      </div>
    )
  }
  return (
    <div data-testid="mastery-row" data-seen="true">
      <Bar value={r.mastery} tone={tone(r.mastery)} label={<span>{r.id} · {r.name} {r.resolved && <Pill tone="good">resolved</Pill>}</span>} right={`${pct(r.mastery)}%`} />
    </div>
  )
}

export default function Dashboard() {
  const lid = learnerId()
  const [data, setData] = useState(null)
  const [empty, setEmpty] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    api.learner(lid).then(setData).catch((e) => (e.status === 404 ? setEmpty(true) : setError(e.message)))
  }, [lid])

  if (error) return <ErrorNote error={error} />
  if (empty) {
    return (
      <Card title="Dashboard">
        <EmptyProgress />
      </Card>
    )
  }
  if (!data) return <p className="text-sm text-muted">Loading…</p>

  const items = summarise(data)
  // with evidence: lowest mastery first, most recently detected breaks ties; the rest keep M1..M8 order
  const seen = items.filter((i) => i.attempts > 0).sort((a, b) => a.mastery - b.mastery || b.last - a.last)
  const unseen = items.filter((i) => i.attempts === 0)
  const visible = expanded ? [...seen, ...unseen] : seen.slice(0, TOP_N)

  return (
    <div className="space-y-6">
      <Card title={<>Mastery by misconception<InfoTip text={HINT} /></>} right={<span className="font-mono text-xs text-muted">{lid}</span>}>
        {visible.length === 0 ? <EmptyProgress /> : (
          <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {visible.map((r) => <MasteryRow key={r.full} r={r} />)}
          </div>
        )}
        <button type="button" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}
          className="mt-4 text-xs text-accent hover:underline">
          {expanded ? 'Show fewer' : `Show all (${MISC.length})`}
        </button>
      </Card>

      <Card title={`Attempt history · ${data.history.length}`}>
        {data.history.length === 0 ? <p className="text-sm text-muted">Nothing yet.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr><th className="py-2 pr-4">When</th><th className="pr-4">Type</th><th className="pr-4">Problem</th><th className="pr-4">Diagnosis</th><th className="pr-4">Tests</th><th className="pr-4">Outcome</th><th>Mastery</th></tr>
              </thead>
              <tbody>
                {[...data.history].reverse().map((h) => (
                  <tr key={h.id} className="border-t border-line">
                    <td className="whitespace-nowrap py-2 pr-4 text-muted">{new Date(h.ts * 1000).toLocaleString()}</td>
                    <td className="pr-4">{h.kind === 'reassess' ? <Pill tone="info">prove it</Pill> : <Pill>submit</Pill>}</td>
                    <td className="pr-4 font-mono text-xs">{h.problem_id}</td>
                    <td className="pr-4">{h.label ? short(h.label) : '-'}</td>
                    <td className={`pr-4 ${h.passed ? 'text-good' : 'text-bad'}`}>{h.passed ? 'pass' : 'fail'}</td>
                    <td className="pr-4">{h.kind === 'reassess' ? (h.resolved ? <Pill tone="good">resolved</Pill> : <Pill tone="warn">not yet</Pill>) : '-'}</td>
                    <td className="tabular-nums text-muted">{h.mastery_after != null ? `${Math.round(h.mastery_after * 100)}%` : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
