const STEPS = ['Write', 'Check', 'Understand', 'Prove it']

// Where the learner is in the loop. `current` = index of the active step; steps before it are done.
export default function StepIndicator({ current, allDone = false }) {
  return (
    <nav aria-label="Your progress on this problem">
      <ol className="grid grid-cols-4 gap-1 sm:gap-2">
        {STEPS.map((s, i) => {
          const done = allDone || i < current
          const active = !allDone && i === current
          return (
            <li key={s} aria-current={active ? 'step' : undefined}
              className={`flex min-h-[44px] flex-col items-center justify-center rounded-lg border px-1 py-1 text-center text-xs font-semibold sm:flex-row sm:gap-2 sm:text-sm ${
                active ? 'border-accent bg-accent/15 text-accent' : done ? 'border-good/40 bg-good/10 text-good' : 'border-line text-muted'}`}>
              <span aria-hidden>{done ? '✓' : i + 1}</span>
              <span>{s}</span>
              {done && <span className="sr-only">(done)</span>}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
