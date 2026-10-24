import { Link } from 'react-router-dom'
import { Info, Lock } from 'lucide-react'
import { ExplainList } from '../components/Verdict'
import { fmtTime } from '../components/bits'
import { readEvaluation } from '../lib/api/normalize'
import { useSession } from '../lib/session'

export default function Approvals() {
  const { events } = useSession()
  const held = events.filter((e) => e.source === 'evaluate' && e.decision?.key === 'approval_required')

  return (
    <div className="page page-approvals">
      <div className="notice is-info" style={{ marginBottom: '1.25rem' }}>
        <p className="notice-title">
          <Info aria-hidden /> Placeholder / Future Integration (Pending Teammate ApprovalManager)
        </p>
        <p>
          Person 2 owns the separate <code>ApprovalManager</code> and authoritative pending-approval state in the architecture. The current backend evaluates policy decisions and returns <code>approval_required</code> (which blocks domain execution), but does not yet expose an approval management or retrieval API.
        </p>
      </div>

      <section className="tiles tiles-hero">
        <div className="tile tile-hold">
          <div className="hold-mark" aria-hidden>
            <span />
            <span />
          </div>
          <h2>Approvals Workflow (Coming in Next Milestone)</h2>
          <p>
            When a high-impact operation (such as closing a parking zone or rerouting critical infrastructure) is evaluated, the policy gateway blocks immediate execution and returns <code>approval_required</code>. The subsequent approval lifecycle (submitting supervisor approval, expiration, and deferred execution) will be integrated once Person 2's approval service is connected.
          </p>
        </div>
        <div className="tile tile-plan">
          <h3>Planned Architecture</h3>
          <ol className="plan-list">
            <li><strong>Authoritative Store:</strong> Person 2's ApprovalManager tracks real pending approvals on the backend.</li>
            <li><strong>Supervisor Review:</strong> Authorized operators will review, approve, or reject pending requests with signed audit records.</li>
            <li><strong>Execution Dispatch:</strong> Approved actions will be dispatched to domain services with an approval receipt.</li>
          </ol>
        </div>
      </section>

      <section className="tile">
        <div className="results-head">
          <h3>Requests with <code>approval_required</code> in this browser session</h3>
          <span className="muted tnum">{held.length} local event{held.length === 1 ? '' : 's'}</span>
        </div>
        <p className="muted" style={{ marginBottom: '1rem', fontSize: '0.85rem' }}>
          Note: These entries represent past requests from the current browser session that received an <code>approval_required</code> decision from the gateway. They are read-only historical records and do not represent a live backend approval queue.
        </p>
        {held.length === 0 ? (
          <div className="empty">
            <p className="empty-title">No held actions in this session.</p>
            <p>
              When a high-impact request in the <Link to="/console/request-tester">request tester</Link> (such as closing a parking zone) returns <code>approval_required</code>, it will be catalogued here as a local read-only session event.
            </p>
          </div>
        ) : (
          <ul className="held-list">
            {held.map((e) => (
              <li key={e.id} className="tile tile-inner">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <p className="muted tnum">{fmtTime(e.at)}</p>
                  <span className="ptag is-fail" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Lock size={12} /> Execution blocked
                  </span>
                </div>
                <ExplainList view={readEvaluation(e.response)} />
                <p className="held-pending">Action blocked — awaiting future approval manager integration</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
