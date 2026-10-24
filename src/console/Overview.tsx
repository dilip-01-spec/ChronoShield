import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, RefreshCw } from 'lucide-react'
import { ErrorNotice, Skeleton, Stat, fmtMs, fmtTime } from '../components/bits'
import { DISPLAY_BASE, ENDPOINTS, describeBase } from '../lib/api/client'
import { useHealth } from '../lib/health'
import { useSession } from '../lib/session'

export default function Overview() {
  const { state, recheck } = useHealth()
  const { events } = useSession()

  const m = useMemo(() => {
    const evals = events.filter((e) => e.source === 'evaluate' && e.ok)
    const tests = events.filter((e) => e.source === 'policy-test' && e.ok)
    const count = (k: string) => evals.filter((e) => e.decision?.key === k).length
    const rtts = evals.map((e) => e.roundTripMs).filter((x): x is number => typeof x === 'number')
    return {
      evals: evals.length,
      allow: count('allow'),
      deny: count('deny'),
      hold: count('approval_required'),
      other: evals.filter((e) => !e.decision || e.decision.key === 'unknown').length,
      avg: rtts.length ? rtts.reduce((a, b) => a + b, 0) / rtts.length : null,
      tests: tests.length,
      lastTest: tests[0]?.summary ?? null,
      errors: events.filter((e) => !e.ok).length,
    }
  }, [events])

  const total = Math.max(1, m.allow + m.deny + m.hold + m.other)

  return (
    <div className="page page-overview">
      <section className="tiles tiles-hero">
        <div className={`tile tile-conn brackets is-${state.status}`}>
          <div className="conn-top">
            <span className="status-dot big-dot" aria-hidden />
            <h2>{state.status === 'online' ? 'Gateway connected' : state.status === 'offline' ? 'Gateway offline' : 'Checking the gateway…'}</h2>
          </div>
          {state.status === 'online' ? (
            <dl className="conn-facts">
              <div>
                <dt>API</dt>
                <dd>
                  {state.health.title} <span className="muted">v{state.health.version}</span>
                </dd>
              </div>
              <div>
                <dt>Base URL</dt>
                <dd>
                  <code>{describeBase()}</code>
                </dd>
              </div>
              <div>
                <dt>Round-trip</dt>
                <dd className="tnum">
                  {fmtMs(state.health.roundTripMs)} <span className="muted">via {state.health.healthPath ? `GET ${state.health.healthPath}` : 'GET /openapi.json'}</span>
                </dd>
              </div>
              <div>
                <dt>Checked</dt>
                <dd className="tnum">{fmtTime(state.health.checkedAt)}</dd>
              </div>
            </dl>
          ) : null}
          {state.status === 'offline' ? <ErrorNotice error={state.error} /> : null}
          {state.status === 'checking' ? <Skeleton rows={2} height={40} /> : null}
          <button type="button" className="btn btn-quiet" onClick={() => void recheck()}>
            <RefreshCw aria-hidden /> Check again
          </button>
        </div>

        <Link to="/console/policy-testing" className="tile tile-action is-accent">
          <span className="tile-action-title">Run the policy tests</span>
          <span>Six predefined cases against the current policy.</span>
          <ArrowRight size={28} aria-hidden />
        </Link>
        <Link to="/console/request-tester" className="tile tile-action">
          <span className="tile-action-title">Send a request</span>
          <span>One proposed agent call, decided by the gateway.</span>
          <ArrowRight size={28} aria-hidden />
        </Link>
      </section>

      <section className="tiles tiles-stats" aria-label="This session">
        <div className="tile">
          <Stat label="Requests evaluated" value={m.evals} note="this session" />
        </div>
        <div className="tile">
          <Stat label="Policy test runs" value={m.tests} note={m.lastTest ? `last: ${m.lastTest}` : 'none yet'} />
        </div>
        <div className="tile">
          <Stat label="Average round-trip" value={m.avg === null ? '—' : fmtMs(m.avg)} note="browser to gateway and back" />
        </div>
        <div className="tile tile-split">
          <p className="tile-k">Decisions this session</p>
          <div className="split-bar" role="img" aria-label={`${m.allow} allowed, ${m.deny} denied, ${m.hold} approval required`}>
            {m.allow ? <span className="is-allow" style={{ flexGrow: m.allow / total }} /> : null}
            {m.deny ? <span className="is-deny" style={{ flexGrow: m.deny / total }} /> : null}
            {m.hold ? <span className="is-hold" style={{ flexGrow: m.hold / total }} /> : null}
            {m.other ? <span className="is-other" style={{ flexGrow: m.other / total }} /> : null}
            {m.evals === 0 ? <span className="is-empty" style={{ flexGrow: 1 }} /> : null}
          </div>
          <ul className="split-legend">
            <li>
              <i className="is-allow" /> Allow <b className="tnum">{m.allow}</b>
            </li>
            <li>
              <i className="is-deny" /> Deny <b className="tnum">{m.deny}</b>
            </li>
            <li>
              <i className="is-hold" /> Approval required <b className="tnum">{m.hold}</b>
            </li>
          </ul>
        </div>
      </section>

      <section className="tile">
        <div className="results-head">
          <h3>Endpoints the gateway publishes</h3>
          <a className="btn-ghost" href={`${DISPLAY_BASE}/docs`} target="_blank" rel="noreferrer">
            Open Swagger
          </a>
        </div>
        {state.status === 'online' ? (
          <ul className="ops">
            {state.health.operations.map((o) => {
              const wired = o.path === ENDPOINTS.policyTest || o.path === ENDPOINTS.evaluate
              return (
                <li key={o.method + o.path} className={wired ? 'is-wired' : undefined}>
                  <span className={`method m-${o.method.toLowerCase()}`}>{o.method}</span>
                  <code>{o.path}</code>
                  <span className="muted">{o.summary}</span>
                  {wired ? <span className="wired">Used by this console</span> : null}
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="muted">The list appears once the gateway's OpenAPI document loads.</p>
        )}
      </section>
    </div>
  )
}
