import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Eval from './pages/Eval'
import Home from './pages/Home'
import Insights from './pages/Insights'
import Teach from './pages/Teach'
import { ServerBanner, ServerHealthProvider } from './components/ServerHealth'
import { useTheme } from './theme'

const link = ({ isActive }) =>
  `inline-flex min-h-[44px] items-center rounded-lg px-3 text-sm font-medium transition ${isActive ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`

function ThemeToggle() {
  const [theme, setTheme] = useTheme()
  const next = theme === 'light' ? 'dark' : 'light'
  return (
    <button type="button" onClick={() => setTheme(next)} aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}
      className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-line text-lg hover:bg-raised">
      <span aria-hidden>{theme === 'light' ? '☾' : '☀'}</span>
    </button>
  )
}

export default function App() {
  return (
    <ServerHealthProvider>
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-bg">
        Skip to main content
      </a>
      <header className="sticky top-0 z-10 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-2">
          <NavLink to="/" className="inline-flex min-h-[44px] items-center text-lg font-bold tracking-tight">Re<span className="text-accent">:</span>Learn</NavLink>
          <div className="flex items-center gap-1">
            <nav className="flex flex-wrap gap-1" aria-label="Main">
              <NavLink to="/" end className={link}>Practice</NavLink>
              <NavLink to="/dashboard" className={link}>Progress</NavLink>
              <NavLink to="/teach" className={link}>Teach</NavLink>
              <NavLink to="/eval" className={link}>Accuracy</NavLink>
            </nav>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <ServerBanner />
      <main id="main" tabIndex={-1} className="mx-auto max-w-5xl px-4 py-6 sm:py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="/teach" element={<Teach />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="*" element={<p className="text-muted">Page not found.</p>} />
        </Routes>
      </main>
    </div>
    </ServerHealthProvider>
  )
}
