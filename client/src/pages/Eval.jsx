import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, ErrorNote, Pill } from '../components/ui'
import { short } from '../labels'

const f = (x) => (typeof x === 'number' ? x.toFixed(3) : '-')

function BaselineCard({ b }) {
  if (!b) return <Card title="Our model vs Gemini baseline"><p className="text-sm text-muted">Loading…</p></Card>
  if (b.status !== 'ok') {
    return (
      <Card title="Our model vs Gemini baseline" right={<Pill tone="mute">baseline not run</Pill>}>
        <p className="text-sm text-ink/90">Baseline not run.</p>
        <p className="mt-1 text-sm text-muted">{b.reason} Add <code className="font-mono text-accent">GEMINI_API_KEY</code> to <code className="font-mono">ml/.env</code> and run <code className="font-mono">python baseline.py</code>.</p>
      </Card>
    )
  }
  const rows = [['Accuracy', b.ours.accuracy, b.gemini.accuracy], ['Macro-F1', b.ours.macro_f1, b.gemini.macro_f1],
    ...Object.keys(b.ours.twin_exact).map((k) => [`${k.replace('_', ' vs ')} exact (n=${b.ours.twin_exact[k].n})`, b.ours.twin_exact[k].exact, b.gemini.twin_exact[k]?.exact])]
  return (
    <Card title="Our model vs Gemini baseline" right={<Pill tone="info">{b.gemini_model}</Pill>}>
      <p className="mb-3 text-xs text-muted">
        Same held-out problems, {b.n_unique} unique snippets. Gemini: {b.protocol}. {b.invalid_responses} invalid responses counted as wrong.
        Our model also sees test-execution features Gemini does not.
      </p>
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted"><tr><th className="py-1">Metric</th><th>Our model</th><th>Gemini (zero-shot)</th></tr></thead>
        <tbody>
          {rows.map(([n, a, g]) => (
            <tr key={n} className="border-t border-line"><td className="py-2">{n}</td><td className="tabular-nums">{f(a)}</td><td className="tabular-nums">{f(g)}</td></tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

export default function Eval() {
  const [m, setM] = useState(null)
  const [base, setBase] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.metrics().then(setM).catch((e) => setError(e.message))
    api.baseline().then(setBase).catch(() => setBase({ status: 'not_run', reason: 'Could not load the baseline file.' }))
  }, [])

  if (error) return <ErrorNote error={error} />
  if (!m) return <p className="text-sm text-muted">Loading…</p>
  const h = m.holdout

  return (
    <div className="space-y-6">
      <Card title="Held-out evaluation">
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

      <BaselineCard b={base} />

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
