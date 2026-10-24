import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, ShieldCheck } from 'lucide-react'
import { useHealth } from '../lib/health'
import { describeBase } from '../lib/api/client'
import { fmtMs } from '../components/bits'
import CubeWall from './CubeWall'
import { Scramble, useMagnetic } from './fx'

const Spline = lazy(() => import('@splinetool/react-spline'))
const SCENE = (import.meta.env.VITE_SPLINE_SCENE ?? '').trim()

export const NAV_LINKS = [
  { id: 'problem', label: 'Problem' },
  { id: 'how', label: 'How it works' },
  { id: 'demo', label: 'Live demo' },
  { id: 'roadmap', label: 'Roadmap' },
  { id: 'team', label: 'Team' },
]

export function scrollToId(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  const lenis = (window as unknown as { __lenis?: { scrollTo: (t: Element, o?: object) => void } }).__lenis
  if (lenis) lenis.scrollTo(el, { offset: -70, duration: 1.4 })
  else el.scrollIntoView({ behavior: 'smooth' })
}

export function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [active, setActive] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(scrollY > 80)
    onScroll()
    addEventListener('scroll', onScroll, { passive: true })
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(e.target.id)
      },
      { rootMargin: '-45% 0px -50% 0px' },
    )
    NAV_LINKS.forEach((l) => {
      const el = document.getElementById(l.id)
      if (el) io.observe(el)
    })
    return () => {
      removeEventListener('scroll', onScroll)
      io.disconnect()
    }
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('menu-open', open)
  }, [open])

  return (
    <>
      <header className={`nav${scrolled ? ' is-scrolled' : ''}`}>
        <a href="#top" className="wordmark" onClick={(e) => (e.preventDefault(), window.scrollTo({ top: 0, behavior: 'smooth' }))}>
          <ShieldCheck size={22} strokeWidth={1.75} aria-hidden />
          <span>
            CHRONO<b>SHIELD</b>
          </span>
        </a>
        <nav className="nav-links" aria-label="Sections">
          {NAV_LINKS.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              className={active === l.id ? 'is-active' : undefined}
              onClick={(e) => {
                e.preventDefault()
                scrollToId(l.id)
              }}
            >
              {l.label}
            </a>
          ))}
        </nav>
        <Link to="/console" className="nav-cta">
          Open console
        </Link>
        <button type="button" className={`burger${open ? ' is-open' : ''}`} onClick={() => setOpen(!open)} aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open}>
          <span />
          <span />
        </button>
      </header>
      <div className={`menu${open ? ' is-open' : ''}`} aria-hidden={!open}>
        <nav aria-label="Sections">
          {NAV_LINKS.map((l, i) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              tabIndex={open ? 0 : -1}
              style={{ transitionDelay: open ? `${80 + i * 60}ms` : '0ms' }}
              onClick={(e) => {
                e.preventDefault()
                setOpen(false)
                window.setTimeout(() => scrollToId(l.id), 250)
              }}
            >
              {l.label}
            </a>
          ))}
          <Link to="/console" tabIndex={open ? 0 : -1} style={{ transitionDelay: open ? `${80 + NAV_LINKS.length * 60}ms` : '0ms' }}>
            Open console
          </Link>
        </nav>
      </div>
    </>
  )
}

function HeroScene() {
  const weak = typeof navigator !== 'undefined' && ((navigator.hardwareConcurrency ?? 8) <= 4 || innerWidth < 768)
  const [want, setWant] = useState(Boolean(SCENE) && !weak)
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!want || loaded) return
    const t = window.setTimeout(() => setFailed(true), 15000)
    return () => window.clearTimeout(t)
  }, [want, loaded])

  return (
    <div className="hero-scene" data-cursor-hide>
      <CubeWall className={loaded ? 'is-behind' : undefined} />
      {want && !failed ? (
        <Suspense fallback={null}>
          <div className={`spline-layer${loaded ? ' is-loaded' : ''}`}>
            <Spline scene={SCENE} onLoad={() => setLoaded(true)} />
          </div>
        </Suspense>
      ) : null}
      {SCENE && weak && !want ? (
        <button type="button" className="load-3d" onClick={() => setWant(true)}>
          Tap to load the 3D scene
        </button>
      ) : null}
    </div>
  )
}

function GatewayHud() {
  const { state } = useHealth()
  const text =
    state.status === 'online'
      ? `GATEWAY · ONLINE · ${fmtMs(state.health.roundTripMs)}`
      : state.status === 'offline'
        ? 'GATEWAY · OFFLINE — DEMO NEEDS BACKEND'
        : 'GATEWAY · CHECKING…'
  return (
    <p className={`hud-status is-${state.status}`} title={describeBase()}>
      <span className="hud-dot" />
      {text}
    </p>
  )
}

export function Hero() {
  const magnet = useMagnetic<HTMLButtonElement>(8)
  const content = useRef<HTMLDivElement>(null)
  return (
    <section className="hero" id="top">
      <HeroScene />
      <div className="hero-tint" aria-hidden />
      <div className="hud" aria-hidden>
        <span className="hud-corner tl" />
        <span className="hud-corner tr" />
        <span className="hud-corner bl" />
        <span className="hud-corner br" />
        <span className="hud-scan" />
      </div>
      <GatewayHud />
      <div className="hero-content" ref={content}>
        <p className="hero-eyebrow fade-up" style={{ animationDelay: '0.1s' }}>
          CHRONOFORGE 2026 / NITK SURATHKAL
        </p>
        <h1 className="hero-title fade-up" style={{ animationDelay: '0.2s' }}>
          CHRONO
          <span className="accent">
            <Scramble text="SHIELD" delay={500} />
          </span>
        </h1>
        <p className="hero-sub fade-up" style={{ animationDelay: '0.4s' }}>
          Policy before action.
        </p>
        <p className="hero-desc fade-up" style={{ animationDelay: '0.55s' }}>
          AI-native security and governance for autonomous smart cities. Every AI-driven API action is checked against explicit policy — allowed, denied, or held for human approval — before it touches city infrastructure.
        </p>
        <div className="hero-ctas fade-up" style={{ animationDelay: '0.7s' }}>
          <button ref={magnet} type="button" className="btn btn-accent magnetic" onClick={() => scrollToId('demo')}>
            Run the live demo <ArrowRight size={18} aria-hidden />
          </button>
          <Link to="/console" className="btn">
            Open console
          </Link>
        </div>
        <p className="hero-trust fade-up" style={{ animationDelay: '0.85s' }}>
          Team INVOX · Cybersecurity track · FastAPI policy gateway
        </p>
      </div>
      <button type="button" className="scroll-cue" onClick={() => scrollToId('problem')} aria-label="Scroll to the problem">
        <span>SCROLL</span>
        <i>
          <ArrowDown size={12} aria-hidden />
        </i>
      </button>
    </section>
  )
}
