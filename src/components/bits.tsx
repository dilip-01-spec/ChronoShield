import { useState, type ReactNode } from 'react'
import { CircleCheck, CirclePause, CircleHelp, CircleX, Copy, Check } from 'lucide-react'
import type { DecisionView } from '../lib/api/normalize'
import { ApiError, describeBase } from '../lib/api/client'

export function DecisionTag({ d, size = 'md' }: { d: DecisionView | null; size?: 'sm' | 'md' | 'lg' }) {
  if (!d) return <span className={`dtag dtag-${size} is-none`}>No decision field</span>
  const Icon = d.key === 'allow' ? CircleCheck : d.key === 'deny' ? CircleX : d.key === 'approval_required' ? CirclePause : CircleHelp
  return (
    <span className={`dtag dtag-${size} is-${d.key}`} title={`Backend value: ${d.raw}`}>
      <Icon aria-hidden />
      {d.label}
    </span>
  )
}

export function PassTag({ passed }: { passed: boolean | null }) {
  if (passed === null) return <span className="ptag is-unknown">Not reported</span>
  return <span className={`ptag ${passed ? 'is-pass' : 'is-fail'}`}>{passed ? 'Pass' : 'Fail'}</span>
}

export function JsonBlock({ value, label = 'Raw JSON', maxHeight }: { value: unknown; label?: string; maxHeight?: number }) {
  const [copied, setCopied] = useState(false)
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return (
    <div className="jsonblock" data-ui>
      <div className="jsonblock-bar">
        <span>{label}</span>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            try {
              void navigator.clipboard.writeText(text)
              setCopied(true)
              window.setTimeout(() => setCopied(false), 1400)
            } catch {
              /* clipboard unavailable */
            }
          }}
        >
          {copied ? <Check aria-hidden /> : <Copy aria-hidden />} {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre style={maxHeight ? { maxHeight } : undefined}>
        <code>{text}</code>
      </pre>
    </div>
  )
}

export function ErrorNotice({ error, onRetry, compact }: { error: ApiError; onRetry?: () => void; compact?: boolean }) {
  const title =
    error.kind === 'offline'
      ? 'The gateway is not reachable'
      : error.kind === 'timeout'
        ? 'The gateway took too long'
        : error.kind === 'validation'
          ? 'The request shape was rejected'
          : `The gateway answered ${error.status ?? 'with an error'}`
  return (
    <div className={`notice is-${error.kind}${compact ? ' is-compact' : ''}`} role="alert">
      <p className="notice-title">{title}</p>
      <p>{error.message}</p>
      {error.kind === 'offline' && !compact ? (
        <p className="notice-help">
          Start the FastAPI backend so it listens on 127.0.0.1:8000 (for example <code>uvicorn app.main:app --reload --port 8000</code>; check the backend README for the exact module), then try again. Requests go to {describeBase()}.
        </p>
      ) : null}
      {error.issues.length > 0 ? (
        <ul className="notice-issues">
          {error.issues.map((i, n) => (
            <li key={n}>
              <code>{i.loc || 'body'}</code> {i.msg}
            </li>
          ))}
        </ul>
      ) : null}
      {onRetry ? (
        <button type="button" className="btn btn-quiet" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}

export function Skeleton({ rows = 3, height = 56 }: { rows?: number; height?: number }) {
  return (
    <div className="skeleton" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <span key={i} style={{ height }} />
      ))}
    </div>
  )
}

export function fmtMs(ms: number | null | undefined) {
  if (ms === null || ms === undefined) return '—'
  return ms < 10 ? `${ms.toFixed(1)} ms` : `${Math.round(ms)} ms`
}

export function fmtTime(t: number) {
  return new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function Mark({ size = 28 }: { size?: number }) {
  // Four districts on a board; one is denied.
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect x="4" y="4" width="11" height="11" rx="1.5" fill="var(--accent)" />
      <rect x="17" y="4" width="11" height="11" rx="1.5" fill="currentColor" />
      <rect x="4" y="17" width="11" height="11" rx="1.5" fill="currentColor" />
      <rect x="17" y="17" width="11" height="11" rx="1.5" fill="var(--deny)" />
    </svg>
  )
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {note ? <span className="stat-note">{note}</span> : null}
    </div>
  )
}
