import { Bar, Card, Pill } from './ui'
import { nice, short } from '../labels'

export function TestResults({ tests }) {
  if (!tests?.length) return null
  const fmt = (v) => JSON.stringify(v)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="text-muted">
          <tr><th className="py-1 pr-3">Input</th><th className="pr-3">Expected</th><th className="pr-3">Got</th><th></th></tr>
        </thead>
        <tbody className="font-mono">
          {tests.map((t, i) => (
            <tr key={i} className="border-t border-line">
              <td className="py-1.5 pr-3">{t.args.map(fmt).join(', ')}</td>
              <td className="pr-3">{fmt(t.expected)}</td>
              <td className={`pr-3 ${t.ok ? 'text-ink' : 'text-bad'}`}>
                {t.error ? t.error : t.returned_none ? 'None' : fmt(t.got)}
                {t.modified_input && <span className="ml-2 text-warn">(changed its input)</span>}
              </td>
              <td className={t.ok ? 'text-good' : 'text-bad'} aria-label={t.ok ? 'pass' : 'fail'}>{t.ok ? '✓ pass' : '✗ fail'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function DiagnosisCard({ diag }) {
  const ok = diag.label === 'CORRECT'
  const tone = ok ? 'good' : diag.label ? 'bad' : 'warn'
  const top = diag.probabilities
    ? Object.entries(diag.probabilities).sort((a, b) => b[1] - a[1]).slice(0, 3)
    : []
  const passed = diag.test_results?.filter((t) => t.ok).length ?? 0
  return (
    <Card title="Diagnosis" right={<Pill tone={tone}>{diag.label ? short(diag.label) : 'no diagnosis'}</Pill>}>
      {!diag.label ? (
        <p className="text-sm text-warn">{diag.error || 'Your code could not be assessed.'}</p>
      ) : (
        <div className="space-y-5">
          <div>
            <p className="text-lg font-semibold">{ok ? 'Looks correct' : nice(diag.label)}</p>
            <div className="mt-3">
              <Bar value={diag.confidence} tone={tone} label="Model confidence" right={`${Math.round(diag.confidence * 100)}%`} />
            </div>
            {diag.ambiguous && diag.runner_up && (
              <p className="mt-2 text-xs text-warn">
                Close call with {short(diag.runner_up.label)} ({Math.round(diag.runner_up.probability * 100)}%) - these two can look alike.
              </p>
            )}
            {top.length > 1 && (
              <p className="mt-2 text-xs text-muted">
                Next most likely: {top.slice(1).map(([l, p]) => `${short(l)} ${Math.round(p * 100)}%`).join(' · ')}
              </p>
            )}
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Evidence</h3>
            <ul className="space-y-1.5 text-sm">
              {diag.evidence.map((e, i) => (
                <li key={i} className="flex gap-2">
                  <span className={e.kind === 'behavior' ? 'text-warn' : 'text-accent'} aria-hidden>●</span>
                  <span className="text-ink/90">{e.text}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <div className="mt-5">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
          Tests {diag.test_results?.length ? `· ${passed}/${diag.test_results.length} passing` : ''}
        </h3>
        <TestResults tests={diag.test_results} />
      </div>
    </Card>
  )
}
