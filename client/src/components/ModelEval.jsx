import { Card, Pill } from './ui'
import { short } from '../labels'

// Eval-page sections for docs/model_comparison.json, ablation.json, calibration.json and the Realistic confusion matrix.
// Every number comes from those committed files (served by GET /metrics).

const f3 = (x) => (typeof x === 'number' ? x.toFixed(3) : '-')
const ci = (c) => (c ? `${c[0].toFixed(2)}-${c[1].toFixed(2)}` : '')

export function ComparisonCard({ c }) {
  if (!c) return null
  const twinKeys = Object.keys(c.models[0].realistic.twin_pairs)
  const classes = Object.keys(c.models[0].realistic.per_class_recall)
  return (
    <Card title="Model comparison (same split)" right={<Pill tone="info">baselines</Pill>}>
      <p className="mb-4 text-sm text-muted">{c.description}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted">
            <tr><th className="py-2 pr-3">Model</th><th className="pr-3">Realistic accuracy (95% CI)</th><th className="pr-3">Realistic macro-F1 (95% CI)</th>
              {twinKeys.map((k) => <th key={k} className="pr-3">Twins {k.replace('_', '/')}</th>)}<th className="pr-3">Held-out accuracy</th><th>Held-out macro-F1</th></tr>
          </thead>
          <tbody>
            {c.models.map((m) => (
              <tr key={m.model} className="border-t border-line">
                <td className="py-2 pr-3 font-medium">{m.model}</td>
                <td className="pr-3 tabular-nums">{f3(m.realistic.accuracy)} <span className="text-xs text-muted">({ci(m.realistic.bootstrap?.accuracy_ci95)})</span></td>
                <td className="pr-3 tabular-nums">{f3(m.realistic.macro_f1)} <span className="text-xs text-muted">({ci(m.realistic.bootstrap?.macro_f1_ci95)})</span></td>
                {twinKeys.map((k) => <td key={k} className="pr-3 tabular-nums">{f3(m.realistic.twin_pairs[k]?.exact)}</td>)}
                <td className="pr-3 tabular-nums">{f3(m.holdout.accuracy)}</td>
                <td className="tabular-nums">{f3(m.holdout.macro_f1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="mt-3 text-sm">
        <summary className="min-h-[44px] cursor-pointer py-2 text-muted">Per-class recall on the Realistic set</summary>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted"><tr><th className="py-1 pr-3">Model</th>{classes.map((l) => <th key={l} className="pr-2">{short(l)}</th>)}</tr></thead>
            <tbody>
              {c.models.map((m) => (
                <tr key={m.model} className="border-t border-line">
                  <td className="py-2 pr-3">{m.model}</td>
                  {classes.map((l) => <td key={l} className="pr-2 tabular-nums">{m.realistic.per_class_recall[l].toFixed(2)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  )
}

export function AblationCard({ a }) {
  if (!a) return null
  const rows = a.results
  return (
    <Card title="Which signals matter (ablation)" right={<Pill tone="info">macro-F1, Realistic set</Pill>}>
      <p className="mb-4 text-sm text-muted">{a.description}</p>
      <ul className="space-y-3" aria-label="Realistic macro-F1 by feature set">
        {rows.map((r) => (
          <li key={r.features} title={`${r.features}: Realistic macro-F1 ${f3(r.realistic_macro_f1)}, held-out macro-F1 ${f3(r.holdout_macro_f1)}`}>
            <div className="mb-1 flex justify-between gap-3 text-sm">
              <span className={r.features.startsWith('all') ? 'font-semibold' : ''}>{r.features}</span>
              <span className="tabular-nums text-muted">{f3(r.realistic_macro_f1)}</span>
            </div>
            <div className="h-3 rounded bg-raised">
              <div className={`h-full rounded ${r.features.startsWith('all') ? 'bg-accent' : 'bg-accent/60'}`} style={{ width: `${Math.max(1, r.realistic_macro_f1 * 100)}%` }} />
            </div>
          </li>
        ))}
      </ul>
      <details className="mt-3 text-sm">
        <summary className="min-h-[44px] cursor-pointer py-2 text-muted">Table (with held-out problems)</summary>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted"><tr><th className="py-1">Features</th><th>Realistic acc</th><th>Realistic macro-F1</th><th>Held-out macro-F1</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.features} className="border-t border-line">
                <td className="py-2">{r.features}</td><td className="tabular-nums">{f3(r.realistic_accuracy)}</td>
                <td className="tabular-nums">{f3(r.realistic_macro_f1)}</td><td className="tabular-nums">{f3(r.holdout_macro_f1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Card>
  )
}

const MIN_BIN = 10 // bins with fewer samples are drawn hollow and left out of the line (too noisy to read)

// Reliability diagram: x = mean confidence in a bin, y = accuracy in that bin; the diagonal is perfect calibration.
function Reliability({ part, label }) {
  const W = 280, H = 280, P = 36
  const sx = (v) => P + v * (W - 2 * P)
  const sy = (v) => H - P - v * (H - 2 * P)
  const pts = (bins) => bins.filter((b) => b.n > 0)
  const series = [
    { key: 'before', bins: pts(part.bins_before), cls: 'text-muted', ece: part.ece_before, name: 'before (T = 1)' },
    { key: 'after', bins: pts(part.bins_after), cls: 'text-accent', ece: part.ece_after, name: 'after temperature' },
  ]
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1 text-sm font-medium">{label} <span className="text-xs font-normal text-muted">n = {part.n}</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[320px]" role="img" aria-label={`Reliability diagram, ${label}`}>
        <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} className="text-line" stroke="currentColor" strokeDasharray="4 4" />
        <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(0)} className="text-line" stroke="currentColor" />
        <line x1={sx(0)} y1={sy(0)} x2={sx(0)} y2={sy(1)} className="text-line" stroke="currentColor" />
        {[0, 0.5, 1].map((t) => (
          <g key={t} className="fill-current text-muted" fontSize="10">
            <text x={sx(t)} y={H - P + 14} textAnchor="middle">{t}</text>
            <text x={P - 6} y={sy(t) + 3} textAnchor="end">{t}</text>
          </g>
        ))}
        <text x={W / 2} y={H - 4} textAnchor="middle" fontSize="10" className="fill-current text-muted">confidence</text>
        <text x={10} y={H / 2} textAnchor="middle" fontSize="10" className="fill-current text-muted" transform={`rotate(-90 10 ${H / 2})`}>accuracy</text>
        {series.map((s) => {
          const solid = s.bins.filter((b) => b.n >= MIN_BIN)
          return (
            <g key={s.key} className={s.cls}>
              <polyline fill="none" stroke="currentColor" strokeWidth="2" points={solid.map((b) => `${sx(b.confidence)},${sy(b.accuracy)}`).join(' ')} />
              {s.bins.map((b, i) => {
                const r = Math.min(9, 3 + Math.sqrt(b.n) / 3)
                const few = b.n < MIN_BIN
                const tip = <title>{`${s.name}: bin ${b.lo.toFixed(1)}-${b.hi.toFixed(1)}, n=${b.n}${few ? ' (too few to trust)' : ''}, confidence ${b.confidence.toFixed(2)}, accuracy ${b.accuracy.toFixed(2)}`}</title>
                const paint = few ? { fill: 'var(--color-surface)', stroke: 'currentColor', strokeWidth: 1.5 } : { fill: 'currentColor', stroke: 'var(--color-surface)', strokeWidth: 2 }
                return s.key === 'before'
                  ? <rect key={i} x={sx(b.confidence) - r} y={sy(b.accuracy) - r} width={2 * r} height={2 * r} {...paint}>{tip}</rect>
                  : <circle key={i} cx={sx(b.confidence)} cy={sy(b.accuracy)} r={r} {...paint}>{tip}</circle>
              })}
            </g>
          )
        })}
      </svg>
      <p className="mt-1 text-xs text-muted">
        <span className="text-muted">■</span> before: ECE <span className="tabular-nums text-ink">{part.ece_before.toFixed(3)}</span> ·{' '}
        <span className="text-accent">●</span> after: ECE <span className="tabular-nums text-ink">{part.ece_after.toFixed(3)}</span>
      </p>
      <p className="text-xs text-muted">{part.note}</p>
    </figure>
  )
}

export function CalibrationCard({ c }) {
  if (!c) return null
  return (
    <Card title="Calibration" right={<Pill tone="info">T = {c.temperature.toFixed(2)}</Pill>}>
      <p className="mb-4 text-sm text-muted">{c.description} Points on the dashed diagonal are perfectly calibrated; bigger points hold more samples, hollow points have fewer than 10 (too few to read). Hover a point for its bin.</p>
      <div className="grid gap-6 sm:grid-cols-2">
        <Reliability part={c.out_of_fold} label="Out-of-fold (training problems)" />
        <Reliability part={c.holdout} label="Held-out problems" />
      </div>
      {c.holdout.ece_after > c.holdout.ece_before && (
        <p className="mt-4 rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
          On the held-out problems temperature scaling makes calibration worse (ECE {c.holdout.ece_before.toFixed(3)} → {c.holdout.ece_after.toFixed(3)}):
          T was fitted on harder out-of-fold data, so on these easier problems the model likely sounds less sure than it is. Read confidences as rough.
        </p>
      )}
    </Card>
  )
}

export function RealisticConfusion({ r }) {
  const cm = r?.confusion
  if (!cm) return null
  const max = Math.max(...cm.matrix.flat())
  return (
    <Card title="Confusion matrix (Realistic set)" right={<Pill tone="info">serving model</Pill>}>
      <p className="mb-3 text-sm text-muted">{cm.note}. Bootstrap 95% CI ({r.bootstrap.n_resamples} resamples): accuracy {ci(r.bootstrap.accuracy_ci95)}, macro-F1 {ci(r.bootstrap.macro_f1_ci95)}.</p>
      <div className="overflow-x-auto">
        <table className="text-center text-sm tabular-nums">
          <thead className="text-xs text-muted">
            <tr><th className="p-1 text-left">true ↓ / predicted →</th>{cm.cols.map((c) => <th key={c} className="p-1">{short(c)}</th>)}</tr>
          </thead>
          <tbody>
            {cm.rows.map((row, i) => (
              <tr key={row}>
                <th className="p-1 text-left text-xs font-medium text-muted">{short(row)}</th>
                {cm.matrix[i].map((v, j) => {
                  const diag = cm.cols[j] === row
                  const a = v ? 0.15 + 0.85 * (v / max) : 0
                  return (
                    <td key={j} className="h-9 w-10 border border-line p-0" title={`true ${row}, predicted ${cm.cols[j]}: ${v}`}>
                      <div className="flex h-9 w-10 items-center justify-center"
                        style={v ? { background: `color-mix(in srgb, var(--color-${diag ? 'accent' : 'bad'}) ${Math.round(a * 60)}%, transparent)` } : undefined}>
                        {v || ''}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export function ModelCardSection({ m }) {
  const a = m.abstention || {}
  const r = m.realistic || {}
  const u = m.unseen || {}
  const pc = (x) => (typeof x === 'number' ? `${Math.round(x * 100)}%` : '-')
  const rows = [
    ['Model', `${m.model}; features: ${m.feature_set} (no code text). Temperature T = ${m.temperature?.toFixed(2)}.`],
    ['Training data', `${m.data}: ${m.n_train + m.n_holdout} samples from 22 problems (${m.n_train} train / ${m.n_holdout} held out). No real learner code.`],
    ['Labels', 'CORRECT, 8 misconceptions (M1-M8) and OTHER_BUG (a real bug that is none of the 8).'],
    ['Intended use', 'Feedback on short beginner Python functions in this app: pick which lesson to show, or say "not sure". Not for grading, ranking or judging people.'],
    ['Unknown rate', `Answers "not sure" on ${pc(1 - a.coverage_known_oof)} of known-class samples (out-of-fold, by design) and ${r.abstention ? `${r.abstention.flagged_unknown}/${r.n}` : '-'} Realistic snippets; flags ${pc(u.mean_flagged_unknown)} of never-seen mistake types.`],
    ['Known limits', `Synthetic training data written by the same authors as the test sets; one label per submission; ${pc(u.mean_confidently_mislabelled)} of never-seen mistake types still get a confident wrong label; confidences are only roughly calibrated.`],
  ]
  return (
    <Card title="Model card" right={<Pill tone="mute">read before trusting the numbers</Pill>}>
      <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[10rem_1fr]">
        {rows.map(([k, v]) => [<dt key={`${k}t`} className="font-semibold">{k}</dt>, <dd key={`${k}d`} className="text-ink/90">{v}</dd>])}
      </dl>
    </Card>
  )
}
