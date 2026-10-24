import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { resolveRef, type JsonSchema, type OpenApiDoc, type OpenApiParameter } from '../lib/api/openapi'
import type { ValidationIssue } from '../lib/api/client'

type Obj = Record<string, unknown>

export function parseRelaxedJson(input: string): { ok: true; data: unknown } | { ok: false; error: string } {
  const trimmed = input.trim()
  if (!trimmed) return { ok: true, data: {} }
  try {
    return { ok: true, data: JSON.parse(trimmed) }
  } catch (strictErr) {
    try {
      let cleaned = trimmed
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(^|[^\\])\/\/.*$/gm, '$1')
      cleaned = cleaned.replace(/,\s*([}\]])/g, '$1')
      // Replace single-quoted strings: 'val' -> "val"
      cleaned = cleaned.replace(/'([^'\\]*(?:\\.[^'\\]*)*)'/g, (_, inner) => {
        return '"' + inner.replace(/"/g, '\\"').replace(/\\'/g, "'") + '"'
      })
      // Quote unquoted object keys
      cleaned = cleaned.replace(/([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_$-]*)\s*:/g, '$1"$2":')
      // Clean any trailing commas before closing braces again
      cleaned = cleaned.replace(/,\s*([}\]])/g, '$1')
      const parsed = JSON.parse(cleaned)
      return { ok: true, data: parsed }
    } catch {
      return { ok: false, error: (strictErr as Error).message }
    }
  }
}

function typeOf(s: JsonSchema): string {
  const t = Array.isArray(s.type) ? s.type.find((x) => x !== 'null') : s.type
  if (t) return t
  if (s.properties) return 'object'
  if (s.enum) return 'string'
  return 'any'
}

function humanize(key: string) {
  const s = key.replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

interface FieldProps {
  doc: OpenApiDoc
  name: string
  path: string
  schema: JsonSchema
  required: boolean
  value: unknown
  onChange: (v: unknown) => void
  issues: ValidationIssue[]
}

function Field({ doc, name, path, schema: raw, required, value, onChange, issues }: FieldProps) {
  const id = useId()
  const s = resolveRef(doc, raw)
  const t = typeOf(s)
  const label = s.title && s.title !== name ? s.title : humanize(name)
  const issue = issues.find((i) => i.loc === path || i.loc.endsWith(`.${path}`))
  const help = s.description

  if (t === 'object' && s.properties) {
    const obj = (value && typeof value === 'object' ? value : {}) as Obj
    const req = new Set(s.required ?? [])
    return (
      <fieldset className="sf-group">
        <legend>{label}</legend>
        {Object.entries(s.properties).map(([k, child]) => (
          <Field
            key={k}
            doc={doc}
            name={k}
            path={`${path}.${k}`}
            schema={child}
            required={req.has(k)}
            value={obj[k]}
            issues={issues}
            onChange={(v) => {
              const next = { ...obj }
              if (v === undefined || v === '') delete next[k]
              else next[k] = v
              if (Object.keys(next).length === 0 && !required) {
                onChange(undefined)
              } else {
                onChange(next)
              }
            }}
          />
        ))}
      </fieldset>
    )
  }

  let control
  if (s.enum?.length) {
    control = (
      <select id={id} value={value === undefined || value === null ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? undefined : s.enum!.find((x) => String(x) === e.target.value))} aria-invalid={Boolean(issue)}>
        <option value="">{required ? 'Choose…' : 'Not set'}</option>
        {s.enum.map((opt) => (
          <option key={String(opt)} value={String(opt)}>
            {String(opt)}
          </option>
        ))}
      </select>
    )
  } else if (t === 'boolean') {
    control = (
      <button type="button" id={id} role="switch" aria-checked={Boolean(value)} className="sf-switch" onClick={() => onChange(!value)}>
        <span />
        {value ? 'True' : 'False'}
      </button>
    )
  } else if (t === 'integer' || t === 'number') {
    control = (
      <input id={id} type="number" inputMode="decimal" value={value === undefined || value === null ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))} aria-invalid={Boolean(issue)} />
    )
  } else if (t === 'string') {
    control = <input id={id} type="text" spellCheck={false} autoComplete="off" value={value === undefined || value === null ? '' : String(value)} placeholder={s.format ?? ''} onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value)} aria-invalid={Boolean(issue)} />
  } else {
    control = <JsonField id={id} value={value} onChange={onChange} invalid={Boolean(issue)} />
  }

  return (
    <div className={`sf-field${issue ? ' has-issue' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required ? <span className="sf-req"> required</span> : null}
      </label>
      {control}
      {issue ? <p className="sf-issue">{issue.msg}</p> : help ? <p className="sf-help">{help}</p> : null}
    </div>
  )
}

function JsonField({ id, value, onChange, invalid }: { id: string; value: unknown; onChange: (v: unknown) => void; invalid: boolean }) {
  const [text, setText] = useState(() => (value === undefined ? '' : JSON.stringify(value, null, 2)))
  const [bad, setBad] = useState(false)

  useEffect(() => {
    setText(value === undefined ? '' : JSON.stringify(value, null, 2))
    setBad(false)
  }, [value])

  return (
    <textarea
      id={id}
      className="mono"
      rows={3}
      value={text}
      aria-invalid={invalid || bad}
      onChange={(e) => {
        setText(e.target.value)
        if (!e.target.value.trim()) {
          setBad(false)
          onChange(undefined)
          return
        }
        const res = parseRelaxedJson(e.target.value)
        if (res.ok) {
          onChange(res.data)
          setBad(false)
        } else {
          setBad(true)
        }
      }}
    />
  )
}

export interface SchemaFormProps {
  doc: OpenApiDoc
  schema: JsonSchema | null
  parameters: OpenApiParameter[]
  body: unknown
  onBody: (v: unknown) => void
  params: Record<string, string>
  onParams: (v: Record<string, string>) => void
  issues?: ValidationIssue[]
  compact?: boolean
}

export function SchemaForm({ doc, schema, parameters, body, onBody, params, onParams, issues = [], compact }: SchemaFormProps) {
  const [mode, setMode] = useState<'form' | 'json'>('form')
  const [raw, setRaw] = useState(() => (body !== undefined ? JSON.stringify(body, null, 2) : ''))
  const [rawErr, setRawErr] = useState<string | null>(null)
  const resolved = useMemo(() => (schema ? resolveRef(doc, schema) : null), [doc, schema])
  const req = new Set(resolved?.required ?? [])
  const lastSerializedBody = useRef(JSON.stringify(body ?? {}))

  // Synchronize raw representation whenever body is updated from outside (preset, replay, form edit)
  useEffect(() => {
    const current = JSON.stringify(body ?? {})
    if (current !== lastSerializedBody.current) {
      lastSerializedBody.current = current
      if (mode === 'form' || !rawErr) {
        setRaw(body !== undefined ? JSON.stringify(body, null, 2) : '')
      }
    }
  }, [body, mode, rawErr])

  const switchToForm = () => {
    if (mode === 'form') return
    if (raw.trim()) {
      const res = parseRelaxedJson(raw)
      if (res.ok) {
        lastSerializedBody.current = JSON.stringify(res.data ?? {})
        onBody(res.data)
        setRawErr(null)
        setMode('form')
      } else {
        setRawErr(`Invalid JSON: ${res.error}. Please correct the syntax before switching to Fields.`)
      }
    } else {
      lastSerializedBody.current = JSON.stringify({})
      onBody({})
      setRawErr(null)
      setMode('form')
    }
  }

  const switchToJson = () => {
    if (mode === 'json') return
    const formatted = JSON.stringify(body ?? {}, null, 2)
    lastSerializedBody.current = JSON.stringify(body ?? {})
    setRaw(formatted)
    setRawErr(null)
    setMode('json')
  }

  const handleRawChange = (text: string) => {
    setRaw(text)
    if (!text.trim()) {
      lastSerializedBody.current = JSON.stringify({})
      setRawErr(null)
      onBody({})
      return
    }
    const res = parseRelaxedJson(text)
    if (res.ok) {
      lastSerializedBody.current = JSON.stringify(res.data ?? {})
      setRawErr(null)
      onBody(res.data)
    } else {
      setRawErr(res.error)
    }
  }

  return (
    <div className={`sf${compact ? ' sf-compact' : ''}`}>
      {parameters.length > 0 && (
        <fieldset className="sf-group">
          <legend>Headers and query</legend>
          {parameters.map((p) => (
            <div className="sf-field" key={`${p.in}-${p.name}`}>
              <label htmlFor={`param-${p.name}`}>
                {p.name}
                <span className="sf-req"> {p.in}{p.required ? ', required' : ''}</span>
              </label>
              <input id={`param-${p.name}`} type="text" autoComplete="off" spellCheck={false} value={params[p.name] ?? ''} onChange={(e) => onParams({ ...params, [p.name]: e.target.value })} />
              {p.description ? <p className="sf-help">{p.description}</p> : null}
            </div>
          ))}
        </fieldset>
      )}

      {resolved ? (
        <>
          <div className="sf-mode" role="tablist" aria-label="Request body editor">
            <button type="button" role="tab" aria-selected={mode === 'form'} onClick={switchToForm}>
              Fields
            </button>
            <button type="button" role="tab" aria-selected={mode === 'json'} onClick={switchToJson}>
              JSON
            </button>
          </div>
          {mode === 'form' ? (
            resolved.properties ? (
              <div className="sf-fields">
                {Object.entries(resolved.properties).map(([k, child]) => (
                  <Field
                    key={k}
                    doc={doc}
                    name={k}
                    path={k}
                    schema={child}
                    required={req.has(k)}
                    value={(body as Obj | undefined)?.[k]}
                    issues={issues}
                    onChange={(v) => {
                      const next = { ...((body as Obj) ?? {}) }
                      if (v === undefined || v === '') delete next[k]
                      else next[k] = v
                      onBody(next)
                    }}
                  />
                ))}
              </div>
            ) : (
              <p className="sf-help">The schema for this body has no named fields. Use the JSON editor.</p>
            )
          ) : (
            <div className="sf-field">
              <label htmlFor="sf-raw">Request body</label>
              <textarea
                id="sf-raw"
                className="mono"
                rows={10}
                spellCheck={false}
                value={raw}
                aria-invalid={Boolean(rawErr)}
                onChange={(e) => handleRawChange(e.target.value)}
              />
              {rawErr ? <p className="sf-issue">Not valid JSON yet: {rawErr}</p> : null}
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
