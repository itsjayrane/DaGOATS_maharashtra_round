import Editor from '@monaco-editor/react'

function defineTheme(monaco) {
  monaco.editor.defineTheme('relearn', {
    base: 'vs-dark', inherit: true, rules: [],
    colors: { 'editor.background': '#0d1320', 'editorLineNumber.foreground': '#4b566b', 'editor.lineHighlightBackground': '#131c2e' },
  })
}

export default function CodeEditor({ value, onChange, height = 280, onSubmit }) {
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
          if (onSubmit) editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, onSubmit)
        }}
        loading={<div className="p-4 text-sm text-muted">Loading editor…</div>}
        options={{ fontSize: 14, minimap: { enabled: false }, scrollBeyondLastLine: false, tabSize: 4, insertSpaces: true,
          padding: { top: 12 }, automaticLayout: true, renderLineHighlight: 'line' }}
      />
    </div>
  )
}
