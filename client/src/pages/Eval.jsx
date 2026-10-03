import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, ErrorNote, Pill } from '../components/ui'
import { short } from '../labels'

const f = (x) => (typeof x === 'number' ? x.toFixed(3) : '-')

const pct = (x) => `${Math.round(x * 100)}%`

function Tile({ label, value, sub, tone }) {
  return (
    <div className="rounded-lg border border-line bg-raised p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className={`mt-1 text-3xl font-semibold tabular-nums ${tone || ''}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  )
}

function Example({ e, kind }) {
  const short = (l) => l.split('_')[0]
  return (
    <div className="rounded-lg border border-line bg-raised p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Pill tone={kind === 'miss' ? 'bad' : 'warn'}>{kind === 'miss' ? 'misclassified' : 'close call'}</Pill>
        <span className="font-mono text-xs text-muted">{e.id} · {e.problem}</span>
        <span className="ml-auto text-xs">
          true <strong>{short(e.true)}</strong>
          {kind === 'miss'
            ? <> → predicted <strong className="text-bad">{short(e.predicted)}</strong> at {pct(e.confidence)}</>
            : <> · only {pct(e.confidence)} sure (runner-up {short(e.runner_up)})</>}
        </span>
      </div>
      <p className="mt-2 text-sm text-ink/90">{e.why || e.note}</p>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-accent">show the code</summary>
        <pre className="mt-2 overflow-x-auto rounded-lg border border-line bg-[#0d1320] p-3 font-mono text-[12px] leading-relaxed">{e.code}</pre>
      </details>
    </div>
  )
}

function RealisticCard({ r }) {
  if (!r) return null
  const [lo, hi] = r.accuracy_ci95
  return (
    <Card title="Realistic set · headline" right={<Pill tone="info">{r.n} hand-written snippets</Pill>}>
      <p className="mb-4 text-sm text-muted">
        Messier code written by hand, with different structures, extra prints, comments, odd names and partial solutions. It is independent of the
        generator templates and was never used for training or model selection; the serving model was evaluated on it once.
      </p>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="Accuracy" value={f(r.accuracy)} sub={`${r.correct}/${r.n} · 95% CI ${lo.toFixed(2)}–${hi.toFixed(2)}`} />
        <Tile label="Macro-F1" value={f(r.macro_f1)} />
        {Object.entries(r.twin_pairs).map(([k, t]) => (
          <Tile key={k} label={`${k.replace('_', ' vs ')} twin accuracy`} value={f(t.exact)} sub={`${t.correct}/${t.n} · ${pct(t.swapped)} swapped with the twin`} />
        ))}
      </div>
      <p className="mt-3 text-xs text-muted">With 40 samples the intervals are wide: read this as an honest check on messier code, not a precise estimate.</p>

      {(r.errors.length > 0 || r.close_calls.length > 0) && (
        <div className="mt-6">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Where it fails, and where it nearly did</h3>
          <div className="space-y-3">
            {r.errors.map((e) => <Example key={e.id} e={e} kind="miss" />)}
            {r.close_calls.map((e) => <Example key={e.id} e={e} kind="close" />)}
          </div>
        </div>
      )}
    </Card>
  )
}

export default function Eval() {
  const [m, setM] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.metrics().then(setM).catch((e) => setError(e.message))
  }, [])

  if (error) return <ErrorNote error={error} />
  if (!m) return <p className="text-sm text-muted">Loading…</p>
  const h = m.holdout

  return (
    <div className="space-y-6">
      <RealisticCard r={m.realistic} />

      <Card title="Template held-out set" right={<Pill tone="warn">optimistic upper bound</Pill>}>
        <div className="mb-4 rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
          {m.caveat} Data are {m.data}; no real learner code was used.
        </div>
        <p className="mb-4 text-sm text-muted">
          {m.model}. Feature set: <span className="text-ink">{m.feature_set}</span>. Held-out problems (never seen in training or selection):{' '}
          <span className="font-mono text-ink">{m.holdout_problems.join(', ')}</span> · {m.n_holdout} samples vs {m.n_train} for training.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[['Accuracy', h.accuracy], ['Macro-F1', h.macro_f1], ...Object.entries(m.cv_macro_f1_train_problems).map(([k, v]) => [`CV · ${k.includes('TF-IDF') ? 'with text' : 'no text'}`, v])].map(([k, v]) => (
            <div key={k} className="rounded-lg border border-line bg-raised p-3">
              <p className="text-xs text-muted">{k}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{f(v)}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Twin pairs (held-out)">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted"><tr><th className="py-1">Pair</th><th>n</th><th>Exact</th><th>Swapped</th></tr></thead>
            <tbody>
              {Object.entries(h.twin_pairs).map(([k, t]) => (
                <tr key={k} className="border-t border-line">
                  <td className="py-2 font-medium">{k.replace('_', ' vs ')}</td>
                  <td className="tabular-nums text-muted">{t.n_a} / {t.n_b}</td>
                  <td className="tabular-nums">{f(t.exact)}</td>
                  <td className="tabular-nums text-muted">{f(t.swapped)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted">Exact = right label of the two; swapped = predicted the twin instead.</p>
        </Card>

        <Card title="Per-problem accuracy">
          <table className="w-full text-left text-sm">
            <tbody>
              {Object.entries(h.per_problem_accuracy).map(([k, v]) => (
                <tr key={k} className="border-t border-line first:border-0"><td className="py-2 font-mono text-xs">{k}</td><td className="text-right tabular-nums">{f(v)}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card title="Per-class report">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted"><tr><th className="py-2">Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead>
            <tbody>
              {Object.entries(h.per_class).map(([l, r]) => (
                <tr key={l} className="border-t border-line">
                  <td className="py-2"><span className="font-medium">{short(l)}</span> <span className="text-xs text-muted">{l}</span></td>
                  <td className="tabular-nums">{r.support ? f(r.precision) : '-'}</td>
                  <td className="tabular-nums">{r.support ? f(r.recall) : '-'}</td>
                  <td className="tabular-nums">{r.support ? f(r.f1) : '-'}</td>
                  <td className="tabular-nums text-muted">{r.support}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">Classes with support 0 had no sample among the held-out problems.</p>
      </Card>

      <Card title="Confusion matrix (held-out problems)">
        <img src={api.confusionUrl()} alt="Confusion matrix of the diagnoser on held-out problems" className="mx-auto max-w-full rounded-lg bg-white p-2" />
      </Card>
    </div>
  )
}
