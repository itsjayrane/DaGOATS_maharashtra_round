import { Fragment } from 'react'
import { findTerms, useGlossary } from '../glossary'
import Term from './Term'

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
  return <button {...p} className={`min-h-[44px] rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed ${v} ${className}`} />
}

const MAX_TERMS = 3 // tooltips per block of text: the first use of each glossary word, at most 3

// plain text with the first use of glossary words turned into tooltips (`seen` is shared across one block)
function Linked({ text, terms, seen }) {
  const hits = findTerms(text, terms).filter((h) => !seen.has(h.key) && seen.size < MAX_TERMS && seen.add(h.key))
  if (!hits.length) return text
  const out = []
  let at = 0
  hits.forEach((h, i) => {
    out.push(<Fragment key={`t${i}`}>{text.slice(at, h.start)}</Fragment>)
    out.push(<Term key={`g${i}`} def={terms[h.key]}>{text.slice(h.start, h.end)}</Term>)
    at = h.end
  })
  out.push(<Fragment key="end">{text.slice(at)}</Fragment>)
  return out
}

// minimal inline renderer: **bold** and `code`, plus glossary tooltips (pass glossary={false} to turn them off)
export function RichText({ text, className = '', glossary = true }) {
  const all = useGlossary()
  const terms = glossary ? all : {}
  const seen = new Set()
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <p className={`leading-relaxed ${className}`}>
      {parts.map((s, i) => {
        if (s.startsWith('**')) return <strong key={i} className="font-semibold text-ink">{s.slice(2, -2)}</strong>
        if (s.startsWith('`')) {
          const c = <code className="rounded bg-raised px-1.5 py-0.5 font-mono text-[0.9em] text-accent">{s.slice(1, -1)}</code>
          const key = Object.keys(terms).find((k) => k === s.slice(1, -1).replace(/\(.*$/, ''))
          if (key && !seen.has(key) && seen.size < MAX_TERMS) { seen.add(key); return <Term key={i} def={terms[key]}>{c}</Term> }
          return <Fragment key={i}>{c}</Fragment>
        }
        return <Fragment key={i}><Linked text={s} terms={terms} seen={seen} /></Fragment>
      })}
    </p>
  )
}

export function CodeBlock({ code, tone, label }) {
  const ring = tone === 'bad' ? 'border-bad/40' : tone === 'good' ? 'border-good/40' : 'border-line'
  const head = tone === 'bad' ? 'text-bad' : tone === 'good' ? 'text-good' : 'text-muted'
  return (
    <div className={`min-w-0 overflow-hidden rounded-lg border ${ring} bg-code`}>
      {label && <div className={`border-b ${ring} px-3 py-1.5 text-xs font-semibold ${head}`}>{label}</div>}
      <pre className="overflow-x-auto p-3 font-mono text-[15px] leading-relaxed text-ink">{code}</pre>
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

// Line-numbered code with highlighted lines (1-based `highlight`), used for the learner's code and the fix.
export function CodeView({ code, highlight = [], tone = 'bad', label, caption, badge }) {
  const lines = String(code).replace(/\n$/, '').split('\n')
  const hl = new Set(highlight)
  const ring = tone === 'bad' ? 'border-bad/40' : 'border-good/40'
  const head = tone === 'bad' ? 'text-bad' : 'text-good'
  const mark = tone === 'bad' ? 'bg-bad/20 border-bad' : 'bg-good/20 border-good'
  return (
    <div className={`min-w-0 overflow-hidden rounded-lg border ${ring} bg-code`}>
      <div className={`flex flex-wrap items-center justify-between gap-2 border-b ${ring} px-3 py-1.5`}>
        <span className={`text-xs font-semibold ${head}`}>{label}</span>
        {badge}
      </div>
      {caption && <div className="border-b border-line px-3 py-1.5 text-xs text-muted">{caption}</div>}
      <div className="overflow-x-auto py-2 font-mono text-[15px] leading-relaxed text-ink" role="region" aria-label={label}>
        <div className="min-w-max">
          {lines.map((l, i) => (
            <div key={i} className={`flex border-l-2 pr-3 ${hl.has(i + 1) ? mark : 'border-transparent'}`} data-hl={hl.has(i + 1) ? 'true' : undefined}>
              <span className="w-8 shrink-0 select-none pr-3 text-right text-muted/70">{i + 1}</span>
              <span className="whitespace-pre">{l || ' '}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
