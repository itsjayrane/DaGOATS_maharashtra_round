import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'

const FALLBACK_AFTER_MS = 5000 // Monaco comes from a CDN; if it has not loaded by then, use a plain textarea

function defineTheme(monaco) {
  monaco.editor.defineTheme('relearn', {
    base: 'vs-dark', inherit: true, rules: [],
    colors: { 'editor.background': '#0d1320', 'editorLineNumber.foreground': '#4b566b', 'editor.lineHighlightBackground': '#131c2e' },
  })
}

export default function CodeEditor({ value, onChange, height = 280, onSubmit }) {
  const [ready, setReady] = useState(false)
  const [fallback, setFallback] = useState(false)

  useEffect(() => {
    if (ready) return undefined
    const t = setTimeout(() => setFallback(true), FALLBACK_AFTER_MS)
    return () => clearTimeout(t)
  }, [ready])

  if (fallback && !ready) {
    return (
      <div className="overflow-hidden rounded-lg border border-line">
        <textarea
          aria-label="Code editor"
          data-testid="code-fallback"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Tab') { // keep focus in the editor and insert 4 spaces, like a code editor
              e.preventDefault()
              const el = e.target
              const s = el.selectionStart
              onChange(el.value.slice(0, s) + '    ' + el.value.slice(el.selectionEnd))
              requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s + 4 })
            } else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && onSubmit) {
              e.preventDefault(); onSubmit()
            }
          }}
          spellCheck={false}
          style={{ height }}
          className="block w-full resize-y bg-[#0d1320] p-3 font-mono text-[15px] leading-relaxed text-ink outline-none"
        />
        <p className="border-t border-line px-3 py-1.5 text-xs text-muted">The full code editor could not load, so this is a simple text box. Your code works the same way.</p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <Editor
        height={height}
        language="python"
        theme="relearn"
        value={value}
        beforeMount={defineTheme}
        onChange={(v) => onChange(v ?? '')}
        onMount={(editor, monaco) => {
          setReady(true)
          if (onSubmit) editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, onSubmit)
        }}
        loading={<div className="p-4 text-sm text-muted">Loading the code editor…</div>}
        options={{ fontSize: 15, minimap: { enabled: false }, scrollBeyondLastLine: false, tabSize: 4, insertSpaces: true,
          padding: { top: 12 }, automaticLayout: true, renderLineHighlight: 'line' }}
      />
    </div>
  )
}
