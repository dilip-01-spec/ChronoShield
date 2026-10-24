import { useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowUpLeft, ClipboardList, FlaskConical, Gauge, Menu, Send, CirclePause, X } from 'lucide-react'
import { Mark, fmtMs } from '../components/bits'
import { useHealth } from '../lib/health'
import { describeBase } from '../lib/api/client'
import '../styles/console.css'
import Overview from './Overview'
import PolicyTesting from './PolicyTesting'
import RequestTester from './RequestTester'
import AuditViewer from './AuditViewer'
import Approvals from './Approvals'

const NAV = [
  { to: 'overview', label: 'Overview', icon: Gauge },
  { to: 'policy-testing', label: 'Policy testing', icon: FlaskConical },
  { to: 'request-tester', label: 'Request tester', icon: Send },
  { to: 'audit', label: 'Audit viewer', icon: ClipboardList },
  { to: 'approvals', label: 'Approvals', icon: CirclePause },
] as const

export function StatusPill() {
  const { state, recheck, polling, setPolling } = useHealth()
  const online = state.status === 'online'
  const text =
    state.status === 'online'
      ? `Connected · ${fmtMs(state.health.roundTripMs)}`
      : state.status === 'offline'
        ? 'Gateway offline'
        : 'Checking gateway…'
  return (
    <div className={`status-pill is-${state.status}`}>
      <button type="button" onClick={() => void recheck()} title={`Re-check ${describeBase()}`}>
        <span className="status-dot" aria-hidden />
        <span>{text}</span>
      </button>
      <button type="button" className="status-poll" onClick={() => setPolling(!polling)} aria-pressed={polling} title="Check every 15 seconds">
        {polling ? 'Auto' : 'Paused'}
      </button>
      <span className="sr-only" aria-live="polite">
        {online ? 'Gateway connected' : state.status === 'offline' ? 'Gateway offline' : ''}
      </span>
    </div>
  )
}

export default function ConsoleApp() {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const current = NAV.find((n) => loc.pathname.includes(n.to))
  useEffect(() => setOpen(false), [loc.pathname])
  useEffect(() => {
    document.title = `${current?.label ?? 'Console'} — ChronoShield`
  }, [current])

  return (
    <div className={`console${open ? ' nav-open' : ''}`}>
      <aside className="c-side" aria-label="Console navigation">
        <Link to="/" className="c-brand">
          <Mark size={26} />
          <span>ChronoShield</span>
        </Link>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={`/console/${n.to}`} className="c-nav-link">
              {({ isActive }) => (
                <>
                  {isActive ? <motion.span layoutId="c-nav-active" className="c-nav-active" transition={{ type: 'spring', stiffness: 520, damping: 40 }} /> : null}
                  <n.icon size={20} strokeWidth={1.75} aria-hidden />
                  <span>{n.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="c-side-foot">
          <Link to="/" className="btn-ghost">
            <ArrowUpLeft aria-hidden /> Back to the site
          </Link>
        </div>
      </aside>
      <button type="button" className="c-scrim" aria-label="Close navigation" onClick={() => setOpen(false)} tabIndex={open ? 0 : -1} />

      <div className="c-main">
        <header className="c-top">
          <button type="button" className="c-menu" onClick={() => setOpen(!open)} aria-label={open ? 'Close navigation' : 'Open navigation'} aria-expanded={open}>
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
          <h1>{current?.label ?? 'Console'}</h1>
          <StatusPill />
        </header>
        <main className="c-page" id="main">
          <Routes>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<Overview />} />
            <Route path="policy-testing" element={<PolicyTesting />} />
            <Route path="request-tester" element={<RequestTester />} />
            <Route path="audit" element={<AuditViewer />} />
            <Route path="approvals" element={<Approvals />} />
            <Route path="*" element={<Navigate to="overview" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
