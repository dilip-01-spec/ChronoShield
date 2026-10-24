import { useEffect, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { Send } from 'lucide-react'
import { ErrorNotice, JsonBlock, Skeleton } from '../components/bits'
import { SchemaForm } from '../components/SchemaForm'
import { ExplainList, Pipeline, VerdictStamp } from '../components/Verdict'
import { ENDPOINTS } from '../lib/api/client'
import { DEFAULT_POLICY_INPUTS, readTestRun } from '../lib/api/normalize'
import { useSession } from '../lib/session'
import { useEvaluate } from '../lib/useGateway'

export default function RequestTester() {
  const ev = useEvaluate()
  const { events } = useSession()
  const loc = useLocation() as { state?: { prefill?: unknown; from?: string; token?: string } }

  // Prefill from "Replay in request tester" on the policy testing page.
  useEffect(() => {
    if (loc.state?.prefill !== undefined && ev.schema.state.status === 'ready') {
      ev.setBody(loc.state.prefill)
      if (loc.state.token) {
        ev.setParams((p) => ({ ...p, 'x-auth-token': loc.state!.token! }))
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.state, ev.schema.state.status])

  const cases = useMemo(() => {
    const last = events.find((e) => e.source === 'policy-test' && e.ok)
    if (!last) return []
    return readTestRun(last.response).rows.filter((r) => r.input !== undefined && typeof r.input === 'object')
  }, [events])

  const s = ev.schema.state

  const applyPreset = (key: string) => {
    const preset = DEFAULT_POLICY_INPUTS[key]
    if (!preset) return
    ev.setBody(preset.body)
    if (preset.token) {
      ev.setParams((p) => ({ ...p, 'x-auth-token': preset.token! }))
    } else {
      ev.setParams((p) => {
        const next = { ...p }
        delete next['x-auth-token']
        delete next['authorization']
        return next
      })
    }
  }

  return (
    <div className="page page-tester">
      <section className="tester-grid">
        <div className="tile tile-compose">
          <div className="tile-headline">
            <h2>Compose a request</h2>
            <p className="muted">
              Fields come from the gateway's schema for <code>POST {ENDPOINTS.evaluate}</code>.
            </p>
          </div>
          {loc.state?.from ? <p className="tag-line">Loaded from test case “{loc.state.from}”.</p> : null}

          <div className="sf-field">
            <label htmlFor="load-preset">Quick scenario presets</label>
            <select
              id="load-preset"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) applyPreset(e.target.value)
              }}
            >
              <option value="">Select a scenario preset…</option>
              <option value="authorized_same_district_access">1. Same-district authorized (North operator → North parking) [ALLOW + EXECUTE]</option>
              <option value="cross_district_access_denied">2. Cross-district mismatch (North operator → South parking) [DENY - DISTRICT_MISMATCH]</option>
              <option value="unauthorized_role_operation_denied">3. Role unauthorized (Viewer → Reserve spot) [DENY - ROLE_NOT_AUTHORIZED]</option>
              <option value="high_impact_operation_requires_approval">4. High-impact action (North operator → Close zone) [APPROVAL_REQUIRED]</option>
              <option value="unknown_domain_denied">5. Unknown domain (Admin → Quantum Hyperspace) [400 - UNKNOWN_DOMAIN]</option>
              <option value="unknown_operation_denied">6. Unknown operation (Admin → Teleport Cars) [400 - UNKNOWN_OPERATION]</option>
            </select>
          </div>

          {cases.length > 0 ? (
            <div className="sf-field">
              <label htmlFor="load-case">Load from the last policy test run</label>
              <select
                id="load-case"
                defaultValue=""
                onChange={(e) => {
                  const c = cases[Number(e.target.value)]
                  if (c) ev.setBody(c.input)
                }}
              >
                <option value="">Choose a case from session…</option>
                {cases.map((c, i) => (
                  <option key={c.id + i} value={i}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="notice is-info is-compact" style={{ margin: '0.75rem 0' }}>
            <p className="notice-title" style={{ fontSize: '0.8rem' }}>Identity Proof vs Actor Hint</p>
            <p style={{ fontSize: '0.75rem' }}>
              Actor metadata in the payload is an unverified routing hint. True authorization relies strictly on server-side token resolution via <code>x-auth-token</code> (e.g. <code>token_operator_north</code>, <code>token_operator_south</code>, <code>token_viewer</code>, <code>token_admin</code>).
            </p>
          </div>
          {s.status === 'loading' ? <Skeleton rows={4} height={46} /> : null}
          {s.status === 'error' ? <ErrorNotice error={s.error} onRetry={ev.schema.reload} /> : null}
          {s.status === 'ready' && !ev.op ? (
            <div className="notice is-http">
              <p className="notice-title">This gateway does not list {ENDPOINTS.evaluate}</p>
              <p>The OpenAPI document has no POST operation at that path.</p>
            </div>
          ) : null}
          {s.status === 'ready' && ev.op ? (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                void ev.send()
              }}
            >
              <SchemaForm doc={s.doc} schema={ev.op.bodySchema} parameters={ev.op.parameters} body={ev.body} onBody={ev.setBody} params={ev.params} onParams={ev.setParams} issues={ev.call.status === 'error' ? ev.call.error.issues : []} />
              <button type="submit" className="btn btn-accent send" disabled={ev.call.status === 'loading'}>
                <Send aria-hidden /> {ev.call.status === 'loading' ? 'Sending…' : 'Send through ChronoShield'}
              </button>
            </form>
          ) : null}
        </div>

        <div className="tile tile-path">
          <h2 className="sr-only">Request path</h2>
          <Pipeline call={ev.call} />
        </div>

        <div className="tile tile-verdict brackets">
          <VerdictStamp call={ev.call} />
          {ev.call.status === 'done' ? <ExplainList view={ev.call.view} /> : null}
        </div>
      </section>

      {ev.call.status === 'done' || ev.call.status === 'error' ? (
        <section className="tiles tiles-two">
          <JsonBlock value={ev.op?.bodySchema ? (ev.body ?? {}) : '(no body)'} label="Request body sent" />
          <JsonBlock value={ev.call.status === 'done' ? ev.call.body : (ev.call.error.body ?? ev.call.error.message)} label="Response" />
        </section>
      ) : null}
    </div>
  )
}
