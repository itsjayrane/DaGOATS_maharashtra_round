import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Eval from './pages/Eval'
import Home from './pages/Home'
import { ServerBanner, ServerHealthProvider } from './components/ServerHealth'

const link = ({ isActive }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${isActive ? 'bg-raised text-ink' : 'text-muted hover:text-ink'}`

export default function App() {
  return (
    <ServerHealthProvider>
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <NavLink to="/" className="text-lg font-bold tracking-tight">Re<span className="text-accent">:</span>Learn</NavLink>
          <nav className="flex gap-1" aria-label="Main">
            <NavLink to="/" end className={link}>Practice</NavLink>
            <NavLink to="/dashboard" className={link}>Dashboard</NavLink>
            <NavLink to="/eval" className={link}>Eval</NavLink>
          </nav>
        </div>
      </header>
      <ServerBanner />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="*" element={<p className="text-muted">Page not found.</p>} />
        </Routes>
      </main>
    </div>
    </ServerHealthProvider>
  )
}
