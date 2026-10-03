export function Card({ title, right, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 ${className}`}>
      {(title || right) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

const TONES = {
  good: 'border-good/40 bg-good/10 text-good',
  bad: 'border-bad/40 bg-bad/10 text-bad',
  warn: 'border-warn/40 bg-warn/10 text-warn',
  info: 'border-accent/40 bg-accent/10 text-accent',
  mute: 'border-line bg-raised text-muted',
}

export function Pill({ tone = 'mute', children }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>
}

export function Button({ variant = 'primary', className = '', ...p }) {
  const v = {
    primary: 'bg-accent text-bg hover:brightness-110 disabled:opacity-50',
    ghost: 'border border-line text-ink hover:bg-raised disabled:opacity-50',
  }[variant]
  return <button {...p} className={`rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${v} ${className}`} />
}

// minimal inline renderer: **bold** and `code`
export function RichText({ text, className = '' }) {
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <p className={`leading-relaxed ${className}`}>
      {parts.map((s, i) =>
        s.startsWith('**') ? <strong key={i} className="font-semibold text-ink">{s.slice(2, -2)}</strong>
          : s.startsWith('`') ? <code key={i} className="rounded bg-raised px-1.5 py-0.5 font-mono text-[0.85em] text-accent">{s.slice(1, -1)}</code>
            : <span key={i}>{s}</span>)}
    </p>
  )
}

export function CodeBlock({ code, tone, label }) {
  const ring = tone === 'bad' ? 'border-bad/40' : tone === 'good' ? 'border-good/40' : 'border-line'
  const head = tone === 'bad' ? 'text-bad' : tone === 'good' ? 'text-good' : 'text-muted'
  return (
    <div className={`min-w-0 overflow-hidden rounded-lg border ${ring} bg-[#0d1320]`}>
      {label && <div className={`border-b ${ring} px-3 py-1.5 text-xs font-semibold ${head}`}>{label}</div>}
      <pre className="overflow-x-auto p-3 font-mono text-[13px] leading-relaxed text-ink">{code}</pre>
    </div>
  )
}

export function Bar({ value, tone = 'info', label, right }) {
  const pct = Math.max(0, Math.min(1, value ?? 0)) * 100
  const fill = { info: 'bg-accent', good: 'bg-good', bad: 'bg-bad', warn: 'bg-warn' }[tone]
  return (
    <div>
      {(label || right) && (
        <div className="mb-1 flex justify-between text-xs">
          <span className="text-ink">{label}</span>
          <span className="tabular-nums text-muted">{right}</span>
        </div>
      )}
      <div className="h-2 overflow-hidden rounded-full bg-raised" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-full rounded-full ${fill} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <div role="alert" className="rounded-lg border border-bad/40 bg-bad/10 p-3 text-sm text-bad">{error}</div>
}
