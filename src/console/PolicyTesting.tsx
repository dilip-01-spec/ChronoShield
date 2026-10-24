import { Fragment, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, ChevronDown, Play } from 'lucide-react'
import { DecisionTag, ErrorNotice, JsonBlock, PassTag, Skeleton, fmtMs, fmtTime } from '../components/bits'
import { SchemaForm } from '../components/SchemaForm'
import { ENDPOINTS } from '../lib/api/client'
import { initialValue } from '../lib/api/openapi'
import { DEFAULT_POLICY_INPUTS, type TestRow } from '../lib/api/normalize'
import { usePolicyTests } from '../lib/useGateway'

function Ring({ passed, total }: { passed: number; total: number }) {
  const r = 34
  const c = 2 * Math.PI * r
  const frac = total ? passed / total : 0
  return (
    <svg className="ring" viewBox="0 0 80 80" role="img" aria-label={`${passed} of ${total} passed`}>
      <circle cx="40" cy="40" r={r} className="ring-track" />
      <motion.circle
        cx="40"
        cy="40"
        r={r}
        className={`ring-fill${frac === 1 ? ' is-all' : ''}`}
        strokeDasharray={c}
        initial={{ strokeDashoffset: c }}
        animate={{ strokeDashoffset: c * (1 - frac) }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
      />
    </svg>
  )
}

function CountUp({ value }: { value: number }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setShown(value)
      return
    }
    let raf = 0
    const start = performance.now()
    const from = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / 900)
      const e = 1 - Math.pow(1 - p, 3)
      setShown(Math.round(from + (value - from) * e))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return <>{shown}</>
}

function ResultRow({ row, index }: { row: TestRow; index: number }) {
  const [open, setOpen] = useState(row.passed === false)
  const nav = useNavigate()
  return (
    <motion.li
      className={`trow${row.passed === false ? ' is-fail' : ''}${open ? ' is-open' : ''}`}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.07, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
    >
      <button type="button" className="trow-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="trow-name">{row.name}</span>
        <span className="trow-cell">
          <span className="trow-k">Expected</span>
          <DecisionTag d={row.expected} size="sm" />
        </span>
        <span className="trow-cell">
          <span className="trow-k">Actual</span>
          <DecisionTag d={row.actual} size="sm" />
        </span>
        <span className="trow-cell trow-code">
          <span className="trow-k">Reason code</span>
          <code>{row.reasonCode ?? '—'}</code>
        </span>
        <span className="trow-pass">
          <PassTag passed={row.passed} />
          <ChevronDown className="trow-caret" aria-hidden />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div className="trow-body" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}>
            <div className="trow-inner">
              <div className="trow-msg">
                <p className="trow-k">Message</p>
                <p>{row.message ?? 'The backend did not include a message for this case.'}</p>
                {row.input !== undefined ? (
                  <button
                    type="button"
                    className="btn btn-quiet"
                    onClick={() =>
                      nav('/console/request-tester', {
                        state: {
                          prefill: row.input,
                          from: row.name,
                          token: DEFAULT_POLICY_INPUTS[row.name]?.token,
                        },
                      })
                    }
                  >
                    Replay in request tester <ArrowRight aria-hidden />
                  </button>
                ) : null}
              </div>
              <JsonBlock value={row.raw} label="This case, as returned" maxHeight={280} />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.li>
  )
}

export default function PolicyTesting() {
  const { schema, op, call, run, history } = usePolicyTests()
  const [body, setBody] = useState<unknown>(undefined)
  const [params, setParams] = useState<Record<string, string>>({})
  const [showRaw, setShowRaw] = useState(false)
  const needsInput = Boolean(op?.bodySchema || op?.parameters.length)

  useEffect(() => {
    if (schema.state.status === 'ready' && op?.bodySchema && body === undefined) {
      setBody(op.bodyExample ?? initialValue(schema.state.doc, op.bodySchema) ?? {})
    }
  }, [schema.state, op, body])

  const view = call.status === 'done' ? call.view : null
  const loading = call.status === 'loading'
  const missingEndpoint = schema.state.status === 'ready' && !op

  const summary = useMemo(() => {
    if (!view) return null
    return { total: view.total, passed: view.passed, failed: view.failed, unknown: view.unknown }
  }, [view])

  return (
    <div className="page page-tests">
      <section className="tiles tiles-hero">
        <div className="tile tile-lead brackets">
          <h2>Pre-deployment authorization tests</h2>
          <p>
            Runs the backend's predefined cases against the current policy before anything ships. Every decision, reason code and message below comes straight from <code>POST {ENDPOINTS.policyTest}</code>.
          </p>
          <div className="tile-actions">
            <button type="button" className="btn btn-accent" onClick={() => void run(body, params)} disabled={loading || schema.state.status === 'loading'}>
              <Play aria-hidden /> {loading ? 'Running…' : call.status === 'done' ? 'Run again' : 'Run policy tests'}
            </button>
            {call.status === 'done' ? (
              <span className="muted">
                Last run {fmtTime(call.at)} · HTTP {call.httpStatus} · {fmtMs(call.roundTripMs)} round-trip
              </span>
            ) : null}
          </div>
        </div>
        <div className="tile tile-ring">
          {summary ? <Ring passed={summary.passed} total={summary.total} /> : <div className="ring ring-empty" aria-hidden />}
          <div>
            <p className="big tnum">{summary ? `${summary.passed}/${summary.total}` : '—'}</p>
            <p className="muted">{summary ? (summary.failed === 0 && summary.unknown === 0 ? 'Every case passed' : `${summary.failed} failed${summary.unknown ? `, ${summary.unknown} not reported` : ''}`) : 'No run yet'}</p>
          </div>
        </div>
        <div className={`tile tile-count${summary ? ' is-pass' : ''}`}>
          <span className="big tnum">{summary ? <CountUp value={summary.passed} /> : '—'}</span>
          <span>Passed</span>
        </div>
        <div className={`tile tile-count${summary && summary.failed > 0 ? ' is-fail' : ''}`}>
          <span className="big tnum">{summary ? <CountUp value={summary.failed} /> : '—'}</span>
          <span>Failed</span>
        </div>
      </section>

      {needsInput && schema.state.status === 'ready' ? (
        <details className="tile tile-options">
          <summary>Request options from the schema</summary>
          <SchemaForm doc={schema.state.doc} schema={op?.bodySchema ?? null} parameters={op?.parameters ?? []} body={body} onBody={setBody} params={params} onParams={setParams} issues={call.status === 'error' ? call.error.issues : []} />
        </details>
      ) : null}

      {missingEndpoint ? (
        <div className="notice is-http" role="alert">
          <p className="notice-title">This gateway does not list {ENDPOINTS.policyTest}</p>
          <p>The OpenAPI document loaded, but it has no POST operation at that path. Check that the backend version matches the frontend.</p>
        </div>
      ) : null}

      <section className="tile tile-results" aria-live="polite" aria-busy={loading}>
        <div className="results-head">
          <h3>{view ? `${view.rows.length} cases returned` : 'Results'}</h3>
          {call.status === 'done' ? (
            <button type="button" className="btn-ghost" onClick={() => setShowRaw(!showRaw)} aria-expanded={showRaw}>
              {showRaw ? 'Hide' : 'Show'} full response
            </button>
          ) : null}
        </div>

        {call.status === 'idle' && schema.state.status !== 'error' ? (
          <div className="empty">
            <p className="empty-title">No run yet in this session.</p>
            <p>Press “Run policy tests”. The backend defines six cases; each one comes back with its expected and actual decision.</p>
          </div>
        ) : null}
        {schema.state.status === 'error' && call.status === 'idle' ? <ErrorNotice error={schema.state.error} onRetry={schema.reload} /> : null}
        {loading ? <Skeleton rows={6} height={64} /> : null}
        {call.status === 'error' ? <ErrorNotice error={call.error} onRetry={() => void run(body, params)} /> : null}
        {view && view.rows.length === 0 ? (
          <div className="notice is-http">
            <p className="notice-title">The response had no list of cases</p>
            <p>The call succeeded but no array of results was found in it. The full response is below.</p>
          </div>
        ) : null}
        {view && view.rows.length > 0 ? (
          <ol className="trows">
            {view.rows.map((r, i) => (
              <Fragment key={`${call.status === 'done' ? call.at : 0}-${r.id}-${i}`}>
                <ResultRow row={r} index={i} />
              </Fragment>
            ))}
          </ol>
        ) : null}
        {call.status === 'done' && (showRaw || view?.rows.length === 0) ? <JsonBlock value={call.body} label={`POST ${ENDPOINTS.policyTest}`} /> : null}
      </section>

      {history.length > 1 ? (
        <section className="tile">
          <h3>Runs this session</h3>
          <ul className="history">
            {history.map((h) => (
              <li key={h.at}>
                <span className="tnum">{fmtTime(h.at)}</span>
                <span className="tnum">
                  {h.passed}/{h.total} passed
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
