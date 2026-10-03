import { useState } from 'react'
import { Button } from './ui'

const STEPS = [
  { icon: '✍️', title: 'Write a small function', text: 'Pick a problem (start with an Easy one) and write your answer in the editor. Stuck? Press "Get a hint" - up to 3 hints, each a bit more helpful.' },
  { icon: '🔎', title: 'Check it', text: 'Press "Check my code". We run tests on your function and spot WHICH common mistake (if any) caused a wrong answer - in plain words.' },
  { icon: '🏆', title: 'Understand it, then prove it', text: 'See why it went wrong and your own code fixed. Then solve 2 new problems: if the mistake stays gone, it counts as fixed for good.' },
]

// 3-step welcome shown on the first visit (and again from "How it works").
export default function Onboarding({ onDone }) {
  const [i, setI] = useState(0)
  const s = STEPS[i]
  const last = i === STEPS.length - 1
  return (
    <section className="celebrate rounded-xl border border-accent/40 bg-accent/10 p-5" aria-labelledby="onb-title" data-testid="onboarding">
      <p className="text-xs font-semibold uppercase tracking-wide text-accent">Welcome to Re:Learn · step {i + 1} of {STEPS.length}</p>
      <h2 id="onb-title" className="mt-2 text-xl font-bold"><span aria-hidden>{s.icon} </span>{s.title}</h2>
      <p className="mt-2 text-sm text-ink/90" aria-live="polite">{s.text}</p>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2" aria-hidden>
          {STEPS.map((_, k) => <span key={k} className={`h-2.5 w-2.5 rounded-full ${k === i ? 'bg-accent' : 'bg-line'}`} />)}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={onDone}>Skip</Button>
          {i > 0 && <Button variant="ghost" onClick={() => setI(i - 1)}>Back</Button>}
          <Button onClick={() => (last ? onDone() : setI(i + 1))}>{last ? "Let's start" : 'Next'}</Button>
        </div>
      </div>
    </section>
  )
}
