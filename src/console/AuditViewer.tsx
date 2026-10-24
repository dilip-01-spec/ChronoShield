import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Download, Info, Trash2, X } from 'lucide-react'
import { DecisionTag, JsonBlock, fmtMs, fmtTime } from '../components/bits'
import { useSession, type SessionEvent } from '../lib/session'

type Filter = 'all' | 'allow' | 'deny' | 'approval_required' | 'errors'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'allow', label: 'Allowed' },
  { id: 'deny', label: 'Denied' },
  { id: 'approval_required', label: 'Approval required' },
  { id: 'errors', label: 'Errors' },
]

function brief(e: SessionEvent) {
  const body = (e.request as { body?: unknown } | null)?.body ?? e.request
  if (!body || typeof body !== 'object') return '—'
  const s = JSON.stringify(body)
  return s.length > 90 ? `${s.slice(0, 88)}…` : s
}

export default function AuditViewer() {
  const { events, clear } = useSession()
  const [filter, setFilter] = useState<Filter>('all')
  const [source, setSource] = useState<'all' | 'evaluate' | 'policy-test'>('all')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<SessionEvent | null>(null)

  const rows = useMemo(
    () =>
      events.filter((e) => {
        if (source !== 'all' && e.source !== source) return false
        if (filter === 'errors' && e.ok) return false
        if (filter !== 'all' && filter !== 'errors' && e.decision?.key !== filter) return false
        if (q && !JSON.stringify([e.request, e.response, e.error]).toLowerCase().includes(q.toLowerCase())) return false
        return true
      }),
    [events, filter, source, q],
  )

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const sanitizeData = (val: unknown, depth = 0): unknown => {
    if (depth > 6 || val === null || val === undefined) return val
    if (Array.isArray(val)) return val.map((v) => sanitizeData(v, depth + 1))
    if (typeof val === 'object') {
      const out: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
        if (/token|authorization|password|secret|key/i.test(k) && typeof v === 'string') {
          out[k] = v ? `${v.slice(0, 6)}***[REDACTED]` : v
        } else {
          out[k] = sanitizeData(v, depth + 1)
        }
      }
      return out
    }
    return val
  }

  const exportJson = () => {
    const sanitizedEvents = events.map((e) => ({
      ...e,
      request: sanitizeData(e.request),
      response: sanitizeData(e.response),
    }))
    const payload = {
      export_type: 'chronoshield_browser_session_history',
      disclaimer:
        'Client-side browser session events only. This is NOT the authoritative backend audit log. Authoritative audit events remain stored in the backend.',
      exported_at: new Date().toISOString(),
      event_count: sanitizedEvents.length,
      events: sanitizedEvents,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `chronoshield-browser-session-${new Date().toISOString().slice(0, 19)}.json`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="page page-audit">
      <div className="notice is-info">
        <p className="notice-title">
          <Info aria-hidden /> Local session events (Client-side history)
        </p>
        <p>
          The ChronoShield backend records authoritative audit events in its own store, but does not yet expose an audit retrieval API. This view records requests and responses received by this browser during the current session only.
        </p>
      </div>

      <section className="tile">
        <div className="audit-tools">
          <div className="chips" role="group" aria-label="Filter by decision">
            {FILTERS.map((f) => (
              <button key={f.id} type="button" className="chip" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
                {f.label}
              </button>
            ))}
          </div>
          <div className="sf-field audit-source">
            <label htmlFor="src" className="sr-only">
              Source
            </label>
            <select id="src" value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
              <option value="all">Every source</option>
              <option value="evaluate">Runtime requests</option>
              <option value="policy-test">Policy test runs</option>
            </select>
          </div>
          <div className="sf-field audit-search">
            <label htmlFor="q" className="sr-only">
              Search
            </label>
            <input id="q" type="search" placeholder="Search requests and responses" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <button type="button" className="btn btn-quiet" onClick={exportJson} disabled={!events.length} title="Export browser session events (credentials scrubbed)">
            <Download aria-hidden /> Export session JSON
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={clear}
            disabled={!events.length}
            title="Clear local browser session events only. Does not alter server audit logs."
          >
            <Trash2 aria-hidden /> Clear session history
          </button>
        </div>

        {events.length === 0 ? (
          <div className="empty">
            <p className="empty-title">Nothing captured yet.</p>
            <p>Run the policy tests or send a request; every response the gateway returns shows up here.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Source</th>
                  <th>Request</th>
                  <th>Decision</th>
                  <th>Reason code</th>
                  <th>Round-trip</th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence initial={false}>
                  {rows.map((e) => (
                    <motion.tr
                      key={e.id}
                      layout
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      onClick={() => setOpen(e)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(k) => {
                        if (k.key === 'Enter' || k.key === ' ') {
                          k.preventDefault()
                          setOpen(e)
                        }
                      }}
                    >
                      <td className="tnum">{fmtTime(e.at)}</td>
                      <td>{e.source === 'evaluate' ? 'Request' : 'Policy tests'}</td>
                      <td className="cell-req">
                        <code>{e.source === 'evaluate' ? brief(e) : e.summary || '—'}</code>
                      </td>
                      <td>{e.ok ? e.source === 'evaluate' ? <DecisionTag d={e.decision} size="sm" /> : <span className="muted">{e.summary}</span> : <span className="ptag is-fail">{e.status ? `HTTP ${e.status}` : 'Error'}</span>}</td>
                      <td>
                        <code>{e.reasonCode ?? '—'}</code>
                      </td>
                      <td className="tnum">{fmtMs(e.roundTripMs)}</td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
            {rows.length === 0 ? <p className="muted pad">No events match these filters.</p> : null}
          </div>
        )}
      </section>

      <AnimatePresence>
        {open ? (
          <>
            <motion.button type="button" className="drawer-scrim" aria-label="Close details" onClick={() => setOpen(null)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.aside className="drawer" role="dialog" aria-label="Event details" initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', stiffness: 320, damping: 36 }}>
              <div className="drawer-head">
                <h3>{open.source === 'evaluate' ? 'Runtime request' : 'Policy test run'}</h3>
                <button type="button" className="btn-ghost" onClick={() => setOpen(null)} aria-label="Close">
                  <X size={20} />
                </button>
              </div>
              <p className="muted">
                {new Date(open.at).toLocaleString()} · {open.status ? `HTTP ${open.status}` : 'no HTTP status'} · {fmtMs(open.roundTripMs)}
              </p>
              {open.error ? <p className="drawer-err">{open.error}</p> : null}
              <JsonBlock value={open.request} label="Request" />
              <JsonBlock value={open.response} label="Response" />
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
