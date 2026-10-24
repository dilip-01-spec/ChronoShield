import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'

export const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
export const finePointer = () => typeof window !== 'undefined' && window.matchMedia('(hover: hover) and (pointer: fine)').matches

/** Mono section label, e.g. "01 / PROBLEM". */
export function SectionLabel({ n, children }: { n: string; children: ReactNode }) {
  return (
    <p className="s-label" data-reveal>
      <span>{n}</span> / {children}
    </p>
  )
}

/** Boot sequence, first visit only, at most ~1.2s. */
export function Preloader() {
  const [phase, setPhase] = useState<'run' | 'wipe' | 'gone'>(() => {
    try {
      return window.sessionStorage.getItem('cs.booted') || reducedMotion() ? 'gone' : 'run'
    } catch {
      return 'run'
    }
  })
  useEffect(() => {
    if (phase !== 'run') return
    try {
      window.sessionStorage.setItem('cs.booted', '1')
    } catch {
      /* ignore */
    }
    const a = window.setTimeout(() => setPhase('wipe'), 900)
    const b = window.setTimeout(() => setPhase('gone'), 1500)
    return () => {
      window.clearTimeout(a)
      window.clearTimeout(b)
    }
  }, [phase])
  if (phase === 'gone') return null
  return (
    <div className={`boot is-${phase}`} aria-hidden>
      <div className="boot-lines">
        <p style={{ animationDelay: '0ms' }}>&gt; resolving identity…</p>
        <p style={{ animationDelay: '260ms' }}>&gt; loading policy…</p>
        <p style={{ animationDelay: '520ms' }}>
          &gt; gateway online<span className="boot-caret" />
        </p>
      </div>
      <span className="boot-wipe" />
    </div>
  )
}

/** Cyan dot + spring-trailing ring. Desktop with a fine pointer only. */
export function Cursor() {
  const dot = useRef<HTMLDivElement>(null)
  const ring = useRef<HTMLDivElement>(null)
  const [on] = useState(() => finePointer() && !reducedMotion())
  useEffect(() => {
    if (!on) return
    document.documentElement.classList.add('has-cursor')
    let x = innerWidth / 2,
      y = innerHeight / 2,
      rx = x,
      ry = y,
      vx = 0,
      vy = 0,
      raf = 0
    const move = (e: PointerEvent) => {
      x = e.clientX
      y = e.clientY
      const t = e.target as HTMLElement
      const hot = t.closest('a, button, select, input, textarea, summary, [data-hot]')
      const hide = t.closest('[data-cursor-hide]')
      ring.current?.classList.toggle('is-hot', Boolean(hot))
      ring.current?.classList.toggle('is-hidden', Boolean(hide) && !hot)
      dot.current?.classList.toggle('is-hidden', Boolean(hide) && !hot)
    }
    const tick = () => {
      // critically-damped spring toward the pointer
      const k = 0.18,
        d = 0.68
      vx = (vx + (x - rx) * k) * d
      vy = (vy + (y - ry) * k) * d
      rx += vx
      ry += vy
      if (dot.current) dot.current.style.transform = `translate3d(${x}px, ${y}px, 0)`
      if (ring.current) ring.current.style.transform = `translate3d(${rx}px, ${ry}px, 0)`
      raf = requestAnimationFrame(tick)
    }
    addEventListener('pointermove', move, { passive: true })
    raf = requestAnimationFrame(tick)
    return () => {
      removeEventListener('pointermove', move)
      cancelAnimationFrame(raf)
      document.documentElement.classList.remove('has-cursor')
    }
  }, [on])
  if (!on) return null
  return (
    <>
      <div ref={ring} className="cursor-ring" aria-hidden>
        <span />
      </div>
      <div ref={dot} className="cursor-dot" aria-hidden />
    </>
  )
}

export function ScrollProgress() {
  const bar = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const h = document.documentElement.scrollHeight - innerHeight
      const p = h > 0 ? scrollY / h : 0
      if (bar.current) bar.current.style.transform = `scaleX(${p})`
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <div ref={bar} className="progress" aria-hidden />
}

export function Grain() {
  return <div className="grain" aria-hidden />
}

/** Random glyphs settle into the word, once. */
export function Scramble({ text, delay = 300 }: { text: string; delay?: number }) {
  const [out, setOut] = useState(text)
  useEffect(() => {
    if (reducedMotion()) return
    const glyphs = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&/\\<>'
    let raf = 0
    let start = 0
    const dur = 800
    const t0 = window.setTimeout(() => {
      const tick = (t: number) => {
        if (!start) start = t
        const p = Math.min(1, (t - start) / dur)
        const settled = Math.floor(p * text.length)
        setOut(
          text
            .split('')
            .map((c, i) => (i < settled ? c : glyphs[Math.floor(Math.random() * glyphs.length)]))
            .join(''),
        )
        if (p < 1) raf = requestAnimationFrame(tick)
        else setOut(text)
      }
      raf = requestAnimationFrame(tick)
    }, delay)
    return () => {
      window.clearTimeout(t0)
      cancelAnimationFrame(raf)
    }
  }, [text, delay])
  return (
    <span aria-label={text}>
      <span aria-hidden>{out}</span>
    </span>
  )
}

/** Pull an element up to `strength` px toward the pointer while hovered. */
export function useMagnetic<T extends HTMLElement>(strength = 8): RefObject<T | null> {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || !finePointer() || reducedMotion()) return
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      const dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2)
      const dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2)
      el.style.transform = `translate(${dx * strength}px, ${dy * strength}px)`
    }
    const leave = () => {
      el.style.transform = ''
    }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    return () => {
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
    }
  }, [strength])
  return ref
}

/** 3D tilt (max `deg`) plus a cursor-following spotlight via CSS vars --mx/--my. */
export function useTilt<T extends HTMLElement>(deg = 8): RefObject<T | null> {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || !finePointer() || reducedMotion()) return
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      const px = (e.clientX - r.left) / r.width
      const py = (e.clientY - r.top) / r.height
      el.style.setProperty('--mx', `${px * 100}%`)
      el.style.setProperty('--my', `${py * 100}%`)
      el.style.transform = `perspective(900px) rotateX(${(0.5 - py) * deg}deg) rotateY(${(px - 0.5) * deg}deg)`
    }
    const leave = () => {
      el.style.transform = ''
    }
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerleave', leave)
    return () => {
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
    }
  }, [deg])
  return ref
}

export function Tilt({ className, children, deg = 8, as = 'div' }: { className?: string; children: ReactNode; deg?: number; as?: 'div' | 'li' | 'article' }) {
  const ref = useTilt<HTMLElement>(deg)
  const Tag = as as 'div'
  return (
    <Tag ref={ref as RefObject<HTMLDivElement>} className={`tilt ${className ?? ''}`} data-reveal>
      <span className="spot" aria-hidden />
      {children}
    </Tag>
  )
}
