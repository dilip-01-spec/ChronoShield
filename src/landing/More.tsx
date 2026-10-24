import { useLayoutEffect, useRef, useState } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SectionLabel, Tilt } from './fx'

gsap.registerPlugin(ScrollTrigger)

/* ---------------- 05 / WHAT MAKES IT DIFFERENT ---------------- */

const DIFFS = [
  { cls: 'b-a', title: 'One policy, two stages', text: 'The rules you test before deployment are the same rules enforced at runtime, so the two can never drift apart.', anim: 'merge' },
  { cls: 'b-b', title: 'Agent-aware authorization', text: 'An agent proposes; ChronoShield decides. An agent is never its own security authority.', anim: 'agent' },
  { cls: 'b-c', title: 'Resource-boundary testing', text: 'Cross-district record access and admin-only functions are tested on purpose.', anim: 'boundary' },
  { cls: 'b-d', title: 'Explainable decisions', text: 'Every verdict carries the caller, endpoint, resource, rule, decision and reason.', anim: 'log' },
  { cls: 'b-e', title: 'Security regression testing', text: 'Rerun the authorization tests after any policy or API change to catch reopened gaps.', anim: 'rerun' },
]

function Micro({ kind }: { kind: string }) {
  switch (kind) {
    case 'merge':
      return (
        <div className="m-merge" aria-hidden>
          <span className="m-pill">test</span>
          <span className="m-pill">runtime</span>
          <i className="m-arrow a1" />
          <i className="m-arrow a2" />
          <span className="m-file">policy</span>
        </div>
      )
    case 'agent':
      return (
        <div className="m-agent" aria-hidden>
          <span className="m-bot">agent</span>
          <span className="m-to">proposes →</span>
          <span className="m-gw">gateway decides</span>
        </div>
      )
    case 'boundary':
      return (
        <div className="m-boundary" aria-hidden>
          <span>north</span>
          <span>south</span>
          <i />
        </div>
      )
    case 'log':
      return (
        <p className="m-log" aria-hidden>
          <span>caller · endpoint · resource · rule · verdict · reason</span>
        </p>
      )
    default:
      return (
        <div className="m-rerun" aria-hidden>
          <i />
          {[0, 1, 2, 3, 4, 5].map((n) => (
            <b key={n} style={{ animationDelay: `${n * 0.25}s` }} />
          ))}
        </div>
      )
  }
}

export function Different() {
  return (
    <section className="diff" id="different">
      <div className="wrap">
        <SectionLabel n="05">WHAT MAKES IT DIFFERENT</SectionLabel>
        <h2 className="h2" data-reveal>
          Built so agents can't grade their own work.
        </h2>
        <div className="bento">
          {DIFFS.map((d) => (
            <Tilt key={d.title} className={`bento-card ${d.cls}`} deg={6}>
              <span className="conic" aria-hidden />
              <div className="bento-inner">
                <Micro kind={d.anim} />
                <h3>{d.title}</h3>
                <p>{d.text}</p>
              </div>
            </Tilt>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ---------------- 06 / ROADMAP ---------------- */

const PHASES = [
  {
    name: 'Phase 1 — MVP (hackathon)',
    built: true,
    items: ['Security gateway and identity resolution', 'Mock parking service with north and south districts', 'Decisions: allow, deny, approval_required', 'In-memory audit logging', 'Six pre-deployment policy tests', 'Console connected to the live gateway'],
  },
  { name: 'Next — approvals and audit retrieval', built: false, items: ['Human approval workflow for held actions', 'Endpoint to read the audit log'] },
  { name: 'Phase 2 — Smarter detection', built: false, items: ['Suspicious action-sequence detection', 'Contextual risk scoring', 'Prompt-injection and manipulated-instruction guards', 'Rate and anomaly limits per agent'] },
  { name: 'Phase 3 — Real-world integration', built: false, items: ['Kong, Envoy and NGINX connectors', 'OAuth2/OIDC, Keycloak and Azure AD', 'Policy as code with OPA/Rego and CI/CD gates', 'Short-lived, least-privilege tokens per action'] },
  { name: 'Phase 4 — City-scale platform', built: false, items: ['Federated policy across departments', 'Digital-twin red-teaming of city services', 'Real-time SOC dashboard with incident replay', 'Audit reports aligned to NIST, ISO 27001 and IEC 62443'] },
]

const VISION = [
  { t: 'Multi-agent governance', d: 'Control and trace actions when many agents delegate to each other.' },
  { t: 'Learning from incidents', d: 'Turn every blocked attack into a new regression test.' },
  { t: 'Open policy standard', d: 'A reusable format for safe agent-to-infrastructure interaction.' },
  { t: 'Explainability for officials', d: 'Plain-language reasons for every allowed or stopped action.' },
]

export function Roadmap() {
  const root = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.fromTo('.tl-beam', { scaleY: 0 }, { scaleY: 1, ease: 'none', scrollTrigger: { trigger: '.timeline', start: 'top 70%', end: 'bottom 60%', scrub: 0.5 } })
        gsap.utils.toArray<HTMLElement>('.tl-item').forEach((el) => {
          ScrollTrigger.create({ trigger: el, start: 'top 68%', toggleClass: 'is-reached' })
        })
      })
      mm.add('(prefers-reduced-motion: reduce)', () => {
        gsap.set('.tl-beam', { scaleY: 1 })
        gsap.utils.toArray<HTMLElement>('.tl-item').forEach((el) => el.classList.add('is-reached'))
      })
    }, root)
    return () => ctx.revert()
  }, [])
  return (
    <section className="roadmap" id="roadmap" ref={root}>
      <div className="wrap">
        <SectionLabel n="06">ROADMAP</SectionLabel>
        <h2 className="h2" data-reveal>
          From a focused MVP to a city‑scale trust layer.
        </h2>
        <ol className="timeline">
          <span className="tl-line" aria-hidden>
            <span className="tl-beam" />
          </span>
          {PHASES.map((p, i) => (
            <li key={p.name} className={`tl-item ${i % 2 ? 'is-right' : 'is-left'}${p.built ? ' is-built' : ''}`}>
              <span className="tl-node" aria-hidden />
              <div className="tl-card" data-reveal>
                <span className={`tl-badge ${p.built ? 'is-built' : 'is-planned'}`}>{p.built ? 'BUILT' : 'PLANNED'}</span>
                <h3>{p.name}</h3>
                <ul>
                  {p.items.map((it) => (
                    <li key={it}>{it}</li>
                  ))}
                </ul>
              </div>
            </li>
          ))}
        </ol>
        <ul className="vision">
          {VISION.map((v) => (
            <li key={v.t} data-reveal>
              <p className="vision-t">{v.t}</p>
              <p>{v.d}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

/* ---------------- 07 / EXPANSION ---------------- */

const DOMAINS = [
  { id: 'emergency', name: 'Emergency dispatch', text: 'Only authorized agents may reroute ambulances or fire units; every override needs human approval.', at: [1, 1] },
  { id: 'transport', name: 'Public transport', text: 'Block unauthorized schedule or signal changes; keep read-only passenger data apart from operator controls.', at: [1, 4] },
  { id: 'grid', name: 'EV charging & energy grid', text: 'Stop agents from changing tariffs or load balancing outside their assigned zone.', at: [4, 1] },
  { id: 'citizen', name: 'Citizen data portals', text: 'Object-level checks so one citizen’s or district’s records are never exposed to another.', at: [4, 4] },
]

const GRID = 6
const HEIGHTS = Array.from({ length: GRID * GRID }, (_, i) => 18 + ((i * 37) % 7) * 12 + ((i * 13) % 5) * 6)

export function Expansion() {
  const [hover, setHover] = useState(DOMAINS[0].id)
  const current = DOMAINS.find((d) => d.id === hover)!
  const root = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.fromTo('.iso-block', { '--rise': 0 }, { '--rise': 1, duration: 1.2, ease: 'expo.out', stagger: { each: 0.025, from: 'center' }, scrollTrigger: { trigger: '.iso', start: 'top 75%' } })
      })
    }, root)
    return () => ctx.revert()
  }, [])
  const domainAt = (r: number, c: number) => DOMAINS.find((d) => d.at[0] === r && d.at[1] === c)
  return (
    <section className="expansion" id="expansion" ref={root}>
      <div className="wrap exp-grid">
        <div className="exp-copy">
          <SectionLabel n="07">EXPANSION</SectionLabel>
          <h2 className="h2" data-reveal>
            Service-agnostic by design.
          </h2>
          <p className="lead" data-reveal>
            New city domains are added by writing resource definitions and test cases, not by rebuilding the gateway. Choose a district.
          </p>
          <div className="domain-list" role="tablist" aria-label="Planned city services">
            {DOMAINS.map((d) => (
              <button key={d.id} type="button" role="tab" aria-selected={hover === d.id} onClick={() => setHover(d.id)} onMouseEnter={() => setHover(d.id)} onFocus={() => setHover(d.id)}>
                {d.name}
              </button>
            ))}
          </div>
          <div className="domain-card" aria-live="polite">
            <span className="tl-badge is-planned">PLANNED</span>
            <h3>{current.name}</h3>
            <p>{current.text}</p>
          </div>
        </div>
        <div className="iso-stage" aria-hidden>
          <div className="iso">
            {Array.from({ length: GRID * GRID }).map((_, i) => {
              const r = Math.floor(i / GRID)
              const c = i % GRID
              const d = domainAt(r, c)
              const h = d ? 70 : HEIGHTS[i]
              return (
                <div key={i} className={`iso-cell${d ? ' is-domain' : ''}${d && d.id === hover ? ' is-on' : ''}`} onMouseEnter={d ? () => setHover(d.id) : undefined}>
                  <div className="iso-block" style={{ ['--h' as string]: `${h}px` }}>
                    <i className="f-top" />
                    <i className="f-left" />
                    <i className="f-right" />
                  </div>
                  {d ? <span className="dome" /> : null}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---------------- 08 / TEAM ---------------- */

const TEAM = ['Dilip S', 'Manish Jindal', 'Ashish P', 'Sushanth Hegde']

export function Team() {
  return (
    <section className="team" id="team">
      <div className="wrap">
        <SectionLabel n="08">TEAM INVOX</SectionLabel>
        <h2 className="h2" data-reveal>
          Four builders, one gateway.
        </h2>
        <p className="lead" data-reveal>
          Team INVOX · ChronoForge 2026 · NITK Surathkal · Cybersecurity track
        </p>
        <ul className="team-grid">
          {TEAM.map((n, i) => (
            <li key={n}>
              <Tilt className={`member m${i}`}>
                <span className="mono-gram">
                  {n
                    .split(' ')
                    .map((p) => p[0])
                    .join('')}
                </span>
                <p className="member-name">{n}</p>
                <p className="member-role">Team INVOX</p>
              </Tilt>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
