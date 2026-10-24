import { Link } from 'react-router-dom'
import { ArrowRight, RefreshCw, Send } from 'lucide-react'
import { SchemaForm } from '../components/SchemaForm'
import { ExplainList, Pipeline, VerdictStamp } from '../components/Verdict'
import { DecisionTag, Skeleton, fmtTime } from '../components/bits'
import { DISPLAY_BASE } from '../lib/api/client'
import { useHealth } from '../lib/health'
import { useSession } from '../lib/session'
import { useEvaluate } from '../lib/useGateway'
import { SectionLabel } from './fx'

function OfflineTerminal({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="terminal" role="alert">
      <p>
        <span className="t-dim">$</span> curl {DISPLAY_BASE}/openapi.json
      </p>
      <p className="t-red">no response from the gateway</p>
      <p className="t-big">Live demo needs the ChronoShield gateway running at {DISPLAY_BASE.replace(/^https?:\/\//, '')}.</p>
      <p className="t-dim">Start the FastAPI backend on 127.0.0.1:8000, then retry. No verdicts are shown without it.</p>
      <button type="button" className="btn btn-quiet" onClick={onRetry}>
        <RefreshCw size={16} aria-hidden /> Retry
      </button>
    </div>
  )
}

export default function LiveDemo() {
  const ev = useEvaluate()
  const { state, recheck } = useHealth()
  const { events } = useSession()
  const recent = events.filter((e) => e.source === 'evaluate').slice(0, 5)
  const s = ev.schema.state
  const offline = s.status === 'error' || (state.status === 'offline' && s.status !== 'ready')

  return (
    <section className="demo" id="demo">
      <div className="wrap">
        <SectionLabel n="03">LIVE DEMO</SectionLabel>
        <div className="demo-head">
          <h2 className="h2" data-reveal>
            Send a request. Watch it decide.
          </h2>
          <p className="lead" data-reveal>
            This form is built from the gateway's own schema and calls the real <code>POST /api/v1/requests/evaluate</code>. Try a north-district agent on a north record, then on a south one.
          </p>
        </div>

        {offline ? (
          <OfflineTerminal
            onRetry={() => {
              void recheck()
              ev.schema.reload()
            }}
          />
        ) : (
          <div className="demo-grid" data-reveal>
            <div className="demo-panel demo-compose">
              <p className="panel-k">Request</p>
              {s.status === 'loading' ? <Skeleton rows={4} height={46} /> : null}
              {s.status === 'ready' && ev.op ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    void ev.send()
                  }}
                >
                  <SchemaForm compact doc={s.doc} schema={ev.op.bodySchema} parameters={ev.op.parameters} body={ev.body} onBody={ev.setBody} params={ev.params} onParams={ev.setParams} issues={ev.call.status === 'error' ? ev.call.error.issues : []} />
                  <button type="submit" className="btn btn-accent" disabled={ev.call.status === 'loading'}>
                    <Send size={17} aria-hidden /> {ev.call.status === 'loading' ? 'Sending…' : 'Send through ChronoShield'}
                  </button>
                </form>
              ) : null}
              {s.status === 'ready' && !ev.op ? <p className="muted">The gateway's schema has no POST /api/v1/requests/evaluate.</p> : null}
            </div>
            <div className="demo-panel demo-path">
              <p className="panel-k">Path</p>
              <Pipeline call={ev.call} />
            </div>
            <div className="demo-panel demo-verdict">
              <p className="panel-k">Verdict</p>
              <VerdictStamp call={ev.call} compact />
              {ev.call.status === 'done' ? <ExplainList view={{ ...ev.call.view, fields: ev.call.view.fields.filter(([k]) => !['decision'].includes(k)).slice(0, 4) }} /> : null}
            </div>
          </div>
        )}

        <div className="demo-foot">
          <div className="minilog" aria-label="This session's requests">
            {recent.length === 0 ? (
              <p className="muted">Requests you send appear here, newest first.</p>
            ) : (
              recent.map((e) => (
                <p key={e.id}>
                  <span className="t-dim">{fmtTime(e.at)}</span>
                  {e.ok ? <DecisionTag d={e.decision} size="sm" /> : <span className="ptag is-fail">{e.status ? `HTTP ${e.status}` : 'error'}</span>}
                  <code>{e.reasonCode ?? e.error ?? ''}</code>
                </p>
              ))
            )}
          </div>
          <Link to="/console/request-tester" className="link-arrow">
            Open full console <ArrowRight size={18} aria-hidden />
          </Link>
        </div>
      </div>
    </section>
  )
}
