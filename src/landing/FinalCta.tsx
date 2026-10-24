import { useEffect, useLayoutEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import * as THREE from 'three'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { ArrowRight, ExternalLink } from 'lucide-react'
import { reducedMotion } from './fx'

gsap.registerPlugin(ScrollTrigger)

function shieldShape() {
  const s = new THREE.Shape()
  s.moveTo(0, 1.25)
  s.bezierCurveTo(0.55, 1.05, 0.85, 1.02, 1.05, 1.02)
  s.lineTo(1.05, 0.15)
  s.bezierCurveTo(1.05, -0.55, 0.55, -1.0, 0, -1.3)
  s.bezierCurveTo(-0.55, -1.0, -1.05, -0.55, -1.05, 0.15)
  s.lineTo(-1.05, 1.02)
  s.bezierCurveTo(-0.85, 1.02, -0.55, 1.05, 0, 1.25)
  return s
}

function Shield3D() {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = host.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      el.classList.add('no-webgl')
      return
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.6))
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50)
    camera.position.set(0, 0, 7.2)

    const geo = new THREE.ExtrudeGeometry(shieldShape(), { depth: 0.32, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.06, bevelSegments: 4, curveSegments: 40 })
    geo.center()
    const body = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: 0x14191c, metalness: 0.75, roughness: 0.3, emissive: 0x00303a, emissiveIntensity: 0.4 }))
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), new THREE.LineBasicMaterial({ color: 0x00d9f5 }))
    const wire = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x00d9f5, wireframe: true, transparent: true, opacity: 0.06 }))
    wire.scale.setScalar(1.08)
    // inner check mark
    const check = new THREE.Shape()
    check.moveTo(-0.45, 0.05)
    check.lineTo(-0.12, -0.3)
    check.lineTo(0.5, 0.42)
    check.lineTo(0.38, 0.52)
    check.lineTo(-0.12, -0.06)
    check.lineTo(-0.33, 0.17)
    const checkGeo = new THREE.ExtrudeGeometry(check, { depth: 0.12, bevelEnabled: false })
    const mark = new THREE.Mesh(checkGeo, new THREE.MeshBasicMaterial({ color: 0x00d9f5 }))
    mark.position.z = 0.26
    const group = new THREE.Group()
    group.add(body, edges, wire, mark)
    scene.add(group)
    scene.add(new THREE.AmbientLight(0xffffff, 0.3))
    const l1 = new THREE.DirectionalLight(0xffffff, 1.6)
    l1.position.set(-3, 4, 5)
    scene.add(l1)
    const l2 = new THREE.PointLight(0x00d9f5, 18, 12)
    l2.position.set(2.5, -1.5, 3)
    scene.add(l2)

    const tgt = { x: 0, y: 0 }
    const move = (e: PointerEvent) => {
      tgt.x = (e.clientX / innerWidth - 0.5) * 0.9
      tgt.y = (e.clientY / innerHeight - 0.5) * 0.6
    }
    addEventListener('pointermove', move, { passive: true })
    const resize = () => {
      const r = el.getBoundingClientRect()
      renderer.setSize(r.width, r.height, false)
      camera.aspect = r.width / Math.max(1, r.height)
      camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()
    let visible = false
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting))
    io.observe(el)
    const still = reducedMotion()
    let raf = 0
    let t = 0
    const frame = () => {
      raf = requestAnimationFrame(frame)
      if (!visible) return
      t += 0.01
      const spin = still ? 0 : Math.sin(t * 0.6) * 0.5
      group.rotation.y += (tgt.x + spin - group.rotation.y) * 0.05
      group.rotation.x += (tgt.y - group.rotation.x) * 0.05
      group.position.y = still ? 0 : Math.sin(t) * 0.06
      renderer.render(scene, camera)
    }
    // render one frame so the shield shows even before it scrolls into view
    renderer.render(scene, camera)
    frame()
    return () => {
      cancelAnimationFrame(raf)
      removeEventListener('pointermove', move)
      ro.disconnect()
      io.disconnect()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])
  return (
    <div className="shield3d" ref={host}>
      <svg className="shield-fallback" viewBox="-1.3 -1.4 2.6 2.8" aria-hidden>
        <path d="M0 -1.25 C0.55 -1.05 0.85 -1.02 1.05 -1.02 L1.05 -0.15 C1.05 0.55 0.55 1 0 1.3 C-0.55 1 -1.05 0.55 -1.05 -0.15 L-1.05 -1.02 C-0.85 -1.02 -0.55 -1.05 0 -1.25Z" />
      </svg>
    </div>
  )
}

export default function FinalCta() {
  const root = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const ctx = gsap.context(() => {
      const mm = gsap.matchMedia()
      mm.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.from('.cta-word', { yPercent: 110, opacity: 0, duration: 1, ease: 'expo.out', stagger: 0.12, scrollTrigger: { trigger: '.cta-title', start: 'top 80%' } })
      })
    }, root)
    return () => ctx.revert()
  }, [])
  return (
    <section className="cta" ref={root}>
      <Shield3D />
      <div className="wrap cta-inner">
        <h2 className="cta-title">
          {['Controlled.', 'Verifiable.', 'Secure by design.'].map((w) => (
            <span key={w} className="cta-line">
              <span className="cta-word">{w}</span>
            </span>
          ))}
        </h2>
        <p className="lead cta-close" data-reveal>
          ChronoShield aims to make autonomous infrastructure not only intelligent and efficient, but controlled, verifiable, and secure by design.
        </p>
        <div className="cta-btns" data-reveal>
          <Link to="/console" className="btn btn-accent">
            Open console <ArrowRight size={18} aria-hidden />
          </Link>
          <a href="#" className="btn" onClick={(e) => e.preventDefault()} title="Add the repository link before launch">
            View on GitHub <ExternalLink size={16} aria-hidden />
          </a>
        </div>
      </div>
    </section>
  )
}
