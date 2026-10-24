import { useLayoutEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Car, Droplets, Landmark, TrafficCone } from 'lucide-react'
import { SectionLabel, Tilt } from './fx'

gsap.registerPlugin(ScrollTrigger)

const SENTENCE: { w: string; tone?: 'cyan' | 'red' }[] = [
  { w: 'A' },
  { w: 'request' },
  { w: 'can' },
  { w: 'be' },
  { w: 'technically', tone: 'cyan' },
  { w: 'valid', tone: 'cyan' },
  { w: '—' },
  { w: 'and' },
  { w: 'still' },
  { w: 'exceed', tone: 'red' },
  { w: 'the', tone: 'red' },
  { w: 'permissions', tone: 'red' },
  { w: 'of' },
  { w: 'the' },
  { w: 'agent' },
  { w: 'that' },
  { w: 'sent' },
  { w: 'it.' },
]

const SERVICES = [
  { icon: TrafficCone, name: 'Traffic management', text: 'Agents retime signals and reroute flows across junctions.' },
  { icon: Car, name: 'Parking systems', text: 'Agents read and update occupancy and permit records, district by district.', tag: 'Protected in the prototype' },
  { icon: Droplets, name: 'Water distribution', text: 'Agents watch pressure and request valve and pump changes.' },
  { icon: Landmark, name: 'Public infrastructure', text: 'Agents coordinate lighting, utilities and maintenance work.' },
]

const THREATS = ['BROKEN OBJECT LEVEL AUTHORIZATION', 'BROKEN FUNCTION LEVEL AUTHORIZATION', 'EXCESSIVE PRIVILEGES', 'CROSS-DISTRICT ACCESS', 'AGENT AS ITS OWN AUTHORITY']

export default function Problem() {
  const root = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const mm = gsap.matchMedia()
      mm.add('(min-width: 900px) and (prefers-reduced-motion: no-preference)', () => {
        const words = gsap.utils.toArray<HTMLElement>('.pw')
        gsap.set(words, { opacity: 0.12 })
        gsap.to(words, {
          opacity: 1,
          stagger: 0.5,
          ease: 'none',
          scrollTrigger: { trigger: '.problem-pin', start: 'top top', end: '+=130%', scrub: 0.6, pin: true, anticipatePin: 1 },
        })
      })
      mm.add('(max-width: 899px) and (prefers-reduced-motion: no-preference)', () => {
        gsap.from('.pw', { opacity: 0.12, stagger: 0.04, duration: 0.5, scrollTrigger: { trigger: '.problem-sentence', start: 'top 80%' } })
      })
    }, root)
    return () => ctx.revert()
  }, [])

  return (
    <section className="problem" id="problem" ref={root}>
      <div className="problem-pin">
        <div className="wrap">
          <SectionLabel n="01">PROBLEM</SectionLabel>
          <p className="problem-sentence">
            {SENTENCE.map((s, i) => (
              <span key={i} className={`pw${s.tone ? ` is-${s.tone}` : ''}`}>
                {s.w}{' '}
              </span>
            ))}
          </p>
        </div>
      </div>

      <div className="wrap problem-after">
        <p className="problem-lede" data-reveal>
          Smart cities rely on APIs and AI agents for traffic, parking, water and essential services. Misconfigured access control, excessive privileges and weak object- or function-level authorization don't throw errors: they quietly expose records or allow actions nobody approved.
        </p>
        <ul className="services">
          {SERVICES.map((s) => (
            <li key={s.name}>
              <Tilt className="service">
                <s.icon size={28} strokeWidth={1.5} aria-hidden />
                <h3>{s.name}</h3>
                <p>{s.text}</p>
                {s.tag ? <span className="service-tag">{s.tag}</span> : null}
              </Tilt>
            </li>
          ))}
        </ul>
      </div>

      <div className="marquee" aria-label={`Threats: ${THREATS.join(', ')}`}>
        <div className="marquee-track" aria-hidden>
          {[0, 1].map((k) => (
            <span key={k}>
              {THREATS.map((t) => (
                <span key={t}>
                  {t} <i>·</i>{' '}
                </span>
              ))}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
