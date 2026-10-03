import { useId, useState } from 'react'

// A glossary word: dotted underline; its definition shows on hover, keyboard focus or tap. Esc hides it.
export default function Term({ children, def }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" aria-describedby={id} aria-expanded={open}
        onClick={() => setOpen((o) => !o)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false) }}
        className="cursor-help underline decoration-dotted decoration-2 underline-offset-4 decoration-accent/70">
        {children}
      </button>
      <span id={id} role="tooltip"
        className={`${open ? 'block' : 'hidden'} absolute left-0 top-full z-30 mt-1 w-64 max-w-[80vw] rounded-lg border border-line bg-raised p-3 text-xs font-normal normal-case leading-relaxed tracking-normal text-ink shadow-lg`}>
        {def}
      </span>
    </span>
  )
}
