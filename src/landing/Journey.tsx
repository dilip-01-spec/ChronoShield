import { useLayoutEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Bot, Fingerprint, Scale, ShieldHalf, ScrollText } from 'lucide-react'
import { SectionLabel } from './fx'

gsap.registerPlugin(ScrollTrigger)

const STAGES = [
  { icon: Bot, title: 'Agent / request layer', text: 'Receives a proposed API or tool call from an agent or simulated client.', note: '> parking-agent-north proposes GET /parking/south/records/…' },
  { icon: Fingerprint, title: 'Identity & context', text: 'Identifies the caller and reads the requested operation and target resource.', note: '> caller resolved · scope north · resource south' },
  { icon: Scale, title: 'Policy decision engine', text: 'Checks role-, endpoint-, operation- and resource-level allow and deny rules.', note: '> resource district ≠ caller district' },
  { icon: ShieldHalf, title: 'Enforcement gateway', text: 'Allows permitted requests, blocks violations, or routes sensitive actions for approval.', note: '> decision: deny' },
  { icon: ScrollText, title: 'Audit & test layer', text: 'Stores the verdict with its reason, and reruns authorization tests on demand.', note: '> audit written · caller · endpoint · resource · rule · verdict · reason' },
]

export default function Journey() {
  const root = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const mm = gsap.matchMedia()
      mm.add('(min-width: 900px) and (prefers-reduced-motion: no-preference)', () => {
        const track = root.current!.querySelector<HTMLElement>('.j-track')!
        const packet = root.current!.querySelector<HTMLElement>('.j-packet')!
        const dist = () => track.scrollWidth - innerWidth
        const tween = gsap.to(track, {
          x: () => -dist(),
          ease: 'none',
          scrollTrigger: {
            trigger: '.j-pin',
            start: 'top top',
            end: () => `+=${dist()}`,
            scrub: 0.8,
            pin: true,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            onUpdate: (st) => {
              // the packet rides the rail across the whole track
              const p = st.progress
              const railW = track.scrollWidth - innerWidth * 0.5
              packet.style.transform = `translate3d(${innerWidth * 0.25 + p * (railW - innerWidth * 0.25)}px, 0, 0)`
              packet.classList.toggle('is-denied', p > 0.72)
            },
          },
        })
        gsap.utils.toArray<HTMLElement>('.j-panel').forEach((panel) => {
          ScrollTrigger.create({
            trigger: panel,
            containerAnimation: tween,
            start: 'left 62%',
            end: 'right 30%',
            toggleClass: 'is-active',
          })
        })
        ScrollTrigger.create({ trigger: '.j-panel.is-gateway', containerAnimation: tween, start: 'left 55%', toggleClass: { targets: '.j-rails', className: 'is-split' } })
      })
      mm.add('(max-width: 899px), (prefers-reduced-motion: reduce)', () => {
        gsap.utils.toArray<HTMLElement>('.j-panel').forEach((panel) => {
          ScrollTrigger.create({ trigger: panel, start: 'top 75%', toggleClass: { targets: panel, className: 'is-active' }, once: true })
        })
      })
    }, root)
    return () => ctx.revert()
  }, [])

  return (
    <section className="journey" id="how" ref={root}>
      <div className="j-pin">
        <div className="j-head wrap">
          <SectionLabel n="02">HOW IT WORKS</SectionLabel>
          <h2 className="h2">One request, five checks.</h2>
          <p className="j-cap">Illustration: a north-district parking agent asks for a south-district record.</p>
        </div>
        <div className="j-track">
          <svg className="j-rails" aria-hidden preserveAspectRatio="none">
            <line x1="0" y1="50%" x2="100%" y2="50%" className="rail" />
          </svg>
          <div className="j-packet" aria-hidden>
            <span>GET /parking/south/…</span>
          </div>
          {STAGES.map((s, i) => (
            <article key={s.title} className={`j-panel${i === 3 ? ' is-gateway' : ''}`}>
              <span className="j-index">0{i + 1}</span>
              <div className="j-icon">
                <s.icon size={30} strokeWidth={1.5} aria-hidden />
              </div>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
              {i === 3 ? (
                <div className="j-split" aria-hidden>
                  <span className="is-allow">allow</span>
                  <span className="is-deny">deny</span>
                  <span className="is-hold">approval_required</span>
                </div>
              ) : null}
              <p className="j-note">
                <span>{s.note}</span>
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
