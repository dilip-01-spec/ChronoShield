import { useEffect, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { FileCode2, FlaskConical } from 'lucide-react'
import { DecisionTag, PassTag } from '../components/bits'
import { useHealth } from '../lib/health'
import { useSession } from '../lib/session'
import { usePolicyTests } from '../lib/useGateway'
import { SectionLabel, finePointer, reducedMotion } from './fx'

function PolicyCard() {
  const card = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = card.current
    if (!el || !finePointer() || reducedMotion()) return
    const move = (e: PointerEvent) => {
      const x = e.clientX / innerWidth - 0.5
      const y = e.clientY / innerHeight - 0.5
      el.style.transform = `perspective(900px) rotateY(${x * 18}deg) rotateX(${-y * 14}deg) translateZ(0)`
    }
    addEventListener('pointermove', move, { passive: true })
    return () => removeEventListener('pointermove', move)
  }, [])
  return (
    <div className="policy-wrap" aria-hidden>
      <span className="beam beam-l" />
      <span className="beam beam-r" />
      <div className="policy-card" ref={card}>
        <div className="policy-tab">
          <FileCode2 size={16} strokeWidth={1.75} /> policy
        </div>
        <div className="policy-lines">
          <span style={{ width: '62%' }} />
          <span style={{ width: '84%' }} className="is-c" />
          <span style={{ width: '48%' }} />
          <span style={{ width: '72%' }} />
          <span style={{ width: '56%' }} className="is-c" />
          <span style={{ width: '38%' }} />
        </div>
        <p>One policy</p>
      </div>
    </div>
  )
}

export default function TwoStages() {
  const { call, run } = usePolicyTests()
  const { state } = useHealth()
  const { events } = useSession()
  const stream = events.filter((e) => e.source === 'evaluate' && e.ok).slice(0, 7)
  const rows = call.status === 'done' ? call.view.rows : []
  const offline = state.status === 'offline'
  const cells = rows.length ? rows : Array.from({ length: 6 }, () => null)

  return (
    <section className="stages" id="stages">
      <div className="wrap">
        <SectionLabel n="04">ONE POLICY, TWO STAGES</SectionLabel>
        <h2 className="h2" data-reveal>
          Tested before it ships. Enforced when it runs.
        </h2>

        <div className="stages-grid">
          <div className="stage stage-test" data-reveal>
            <p className="panel-k">Before deployment — Test</p>
            <button type="button" className="btn btn-accent" onClick={() => void run()} disabled={call.status === 'loading' || offline}>
              <FlaskConical size={17} aria-hidden /> {call.status === 'loading' ? 'Running…' : rows.length ? 'Run the 6 policy tests again' : 'Run the 6 policy tests'}
            </button>
            {call.status === 'done' ? (
              <p className="stage-sum tnum">
                {call.view.passed}/{call.view.total} passed · from <code>POST /api/v1/policies/test</code>
              </p>
            ) : null}
            {call.status === 'error' ? <p className="stage-err">{call.error.message}</p> : null}
            <ol className={`cells${offline && !rows.length ? ' is-dim' : ''}`}>
              {cells.map((r, i) => (
                <li key={i} className={`cell${r ? ' is-flipped' : ''}`} style={{ transitionDelay: `${i * 90}ms` }}>
                  <div className="cell-face cell-front">
                    <span className="cell-n">{String(i + 1).padStart(2, '0')}</span>
                    <span className="cell-wait">{offline ? 'awaiting backend' : call.status === 'loading' ? 'running…' : 'not run'}</span>
                  </div>
                  <div className={`cell-face cell-back${r?.passed === false ? ' is-fail' : r?.passed ? ' is-pass' : ''}`}>
                    {r ? (
                      <>
                        <span className="cell-name">{r.name}</span>
                        <DecisionTag d={r.actual} size="sm" />
                        <code>{r.reasonCode ?? '—'}</code>
                        <PassTag passed={r.passed} />
                      </>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <PolicyCard />

          <div className="stage stage-run" data-reveal>
            <p className="panel-k">At runtime — Enforce</p>
            <div className="stream">
              <span className="gate-line" aria-hidden />
              {stream.length === 0 ? (
                <p className="muted stream-empty">Send a request in the live demo to see it here.</p>
              ) : (
                <ul>
                  <AnimatePresence initial={false}>
                    {stream.map((e) => (
                      <motion.li key={e.id} layout initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -30 }} transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }} className={`is-${e.decision?.key ?? 'unknown'}`}>
                        <DecisionTag d={e.decision} size="sm" />
                        <code>{e.reasonCode ?? '—'}</code>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
