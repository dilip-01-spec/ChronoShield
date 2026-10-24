import { AnimatePresence, motion } from 'framer-motion'
import { CircleCheck, CirclePause, CircleHelp, CircleX } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { EvaluationView } from '../lib/api/normalize'
import type { CallState } from '../lib/useGateway'
import { ErrorNotice, fmtMs } from './bits'
import '../styles/components.css'

const STAGES = ['Agent request', 'Identity', 'Policy engine', 'Gateway', 'Audit log']

/** Five nodes; a packet runs through them while the real request is in flight. */
export function Pipeline({ call }: { call: CallState<EvaluationView> }) {
  const decision = call.status === 'done' ? (call.view.decision?.key ?? 'unknown') : null
  const state = call.status === 'loading' ? 'running' : call.status === 'done' ? `done is-${decision}` : call.status === 'error' ? 'error' : 'idle'
  return (
    <ol className={`pipe pipe-${state}`} aria-label="Request path through ChronoShield">
      {STAGES.map((s, i) => (
        <li key={s} style={{ ['--i' as string]: i }}>
          <span className="pipe-node" />
          <span className="pipe-label">{s}</span>
        </li>
      ))}
    </ol>
  )
}

export function VerdictStamp({ call, compact }: { call: CallState<EvaluationView>; compact?: boolean }) {
  if (call.status === 'idle') {
    return (
      <div className="stamp is-idle">
        <p className="stamp-word">Waiting</p>
        <p className="stamp-sub">Send a request to see the gateway's decision.</p>
      </div>
    )
  }
  if (call.status === 'loading') {
    return (
      <div className="stamp is-loading" aria-busy="true">
        <p className="stamp-word">Checking</p>
        <p className="stamp-sub">Resolving identity and evaluating policy…</p>
      </div>
    )
  }
  if (call.status === 'error') return <ErrorNotice error={call.error} compact={compact} />
  const d = call.view.decision
  const key = d?.key ?? 'none'
  const executed = call.view.executed
  const Icon = key === 'allow' ? CircleCheck : key === 'deny' ? CircleX : key === 'approval_required' ? CirclePause : CircleHelp

  // Determine user-facing decision title
  let verdictTitle = d ? d.label : 'No decision'
  if (key === 'allow' && executed !== null) {
    verdictTitle = executed ? 'Allowed & Executed' : 'Allowed (Not Executed)'
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={call.at}
        className={`stamp is-${key}`}
        initial={{ clipPath: 'inset(0 100% 0 0)' }}
        animate={{ clipPath: 'inset(0 0% 0 0)' }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        role="status"
        aria-live="polite"
      >
        <motion.p className="stamp-word" initial={{ scale: 1.25, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.15, type: 'spring', stiffness: 260, damping: 18 }}>
          <Icon aria-hidden />
          {verdictTitle}
        </motion.p>
        <p className="stamp-sub">
          {d ? <>Policy decision <code>{d.raw}</code></> : 'The response did not contain a decision field.'} · HTTP {call.httpStatus} · {fmtMs(call.roundTripMs)} round-trip
        </p>

        {key === 'allow' && executed === false ? (
          <p className="stamp-note is-blocked-warn">
            Policy evaluation allowed the action, but execution was <strong>not attempted</strong>. Unauthenticated requests can preview policy decisions but are blocked from executing protected domain operations. Provide an authorization token to execute.
          </p>
        ) : null}

        {key === 'deny' ? (
          <p className="stamp-note is-deny-note">
            Policy evaluation <strong>denied</strong>. Protected service execution was blocked and <strong>has not executed</strong>.
          </p>
        ) : null}

        {key === 'approval_required' ? (
          <p className="stamp-note is-hold-note">
            High-impact action held for human approval. Operation <strong>has not executed</strong>. The approval workflow isn't available yet. <Link to="/console/approvals">Open approvals</Link>
          </p>
        ) : null}
      </motion.div>
    </AnimatePresence>
  )
}

function show(v: unknown) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}

export function ExplainList({ view }: { view: EvaluationView }) {
  const hiddenKeys = new Set(['decision', 'reason_code', 'message', 'executed', 'audit_id', 'request_id', 'result'])

  return (
    <dl className="explain">
      {view.decision ? (
        <div>
          <dt>Decision</dt>
          <dd>
            <code>{view.decision.raw}</code> ({view.decision.label})
          </dd>
        </div>
      ) : null}

      <div>
        <dt>Execution status</dt>
        <dd>
          {view.executed === true ? (
            <span className="badge-status is-exec-true">Executed (Success)</span>
          ) : view.executed === false ? (
            <span className="badge-status is-exec-false">Not executed (Blocked / Not attempted)</span>
          ) : (
            <span className="badge-status is-exec-unknown">—</span>
          )}
        </dd>
      </div>

      {view.reasonCode ? (
        <div>
          <dt>Reason code</dt>
          <dd>
            <code>{view.reasonCode}</code>
          </dd>
        </div>
      ) : null}

      {view.auditId ? (
        <div>
          <dt>Audit ID</dt>
          <dd>
            <code>{view.auditId}</code>
          </dd>
        </div>
      ) : null}

      {view.requestId ? (
        <div>
          <dt>Request ID</dt>
          <dd>
            <code>{view.requestId}</code>
          </dd>
        </div>
      ) : null}

      {view.message ? (
        <div className="explain-wide">
          <dt>Message</dt>
          <dd>{view.message}</dd>
        </div>
      ) : null}

      {view.result !== null && view.result !== undefined ? (
        <div className="explain-wide">
          <dt>Execution result</dt>
          <dd>
            <pre className="explain-obj"><code>{show(view.result)}</code></pre>
          </dd>
        </div>
      ) : null}

      {view.fields
        .filter(([k]) => !hiddenKeys.has(k))
        .map(([k, v]) => (
          <div key={k} className={typeof v === 'object' && v !== null ? 'explain-wide' : undefined}>
            <dt>{k.replace(/_/g, ' ')}</dt>
            <dd>{typeof v === 'object' && v !== null ? <code className="explain-obj">{show(v)}</code> : show(v)}</dd>
          </div>
        ))}
    </dl>
  )
}
