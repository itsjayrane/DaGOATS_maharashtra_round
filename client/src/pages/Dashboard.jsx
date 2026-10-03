import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, learnerId } from '../api'
import { Bar, Card, ErrorNote, Pill } from '../components/ui'
import { MISC, short } from '../labels'

const tone = (m) => (m >= 0.7 ? 'good' : m >= 0.4 ? 'warn' : 'bad')

export default function Dashboard() {
  const lid = learnerId()
  const [data, setData] = useState(null)
  const [empty, setEmpty] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.learner(lid).then(setData).catch((e) => (e.status === 404 ? setEmpty(true) : setError(e.message)))
  }, [lid])

  if (error) return <ErrorNote error={error} />
  if (empty) {
    return (
      <Card title="Dashboard">
        <p className="text-sm text-muted">No attempts yet for <code className="font-mono">{lid}</code>. <Link to="/" className="text-accent hover:underline">Submit a solution</Link> to start.</p>
      </Card>
    )
  }
  if (!data) return <p className="text-sm text-muted">Loading…</p>

  return (
    <div className="space-y-6">
      <Card title="Mastery by misconception" right={<span className="font-mono text-xs text-muted">{lid}</span>}>
        <p className="mb-4 text-xs text-muted">50% = unknown. Evidence of a misconception lowers it; a verified transfer success raises it.</p>
        <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          {MISC.map(([full, id, name]) => {
            const m = data.mastery[full] || { mastery: 0.5, resolved: false }
            return (
              <div key={full}>
                <Bar value={m.mastery} tone={tone(m.mastery)} label={<span>{id} · {name} {m.resolved && <Pill tone="good">resolved</Pill>}</span>} right={`${Math.round(m.mastery * 100)}%`} />
              </div>
            )
          })}
        </div>
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
