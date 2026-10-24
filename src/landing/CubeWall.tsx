// Native WebGL cube wall: the fallback (and offline) version of the Sentinel AI Spline hero.
// Dark cubes on a wall; the ones near the cursor push forward and catch a cyan light.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { reducedMotion } from './fx'

export default function CubeWall({ className }: { className?: string }) {
  const host = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = host.current
    if (!el) return
    const weak = (navigator.hardwareConcurrency ?? 8) <= 4 || innerWidth < 700
    const still = reducedMotion()

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: !weak, alpha: false, powerPreference: 'high-performance' })
    } catch {
      el.classList.add('no-webgl')
      return
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, weak ? 1 : 1.6))
    renderer.setClearColor(0x0a0b0c, 1)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x0a0b0c, 16, 34)
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100)
    camera.position.set(0, -1.2, 18)
    camera.lookAt(0, 0, 0)

    const COLS = weak ? 22 : 34
    const ROWS = weak ? 16 : 22
    const S = 1
    const G = 0.07
    const count = COLS * ROWS
    const geo = new THREE.BoxGeometry(S, S, S * 1.6)
    const mat = new THREE.MeshStandardMaterial({ color: 0x1b2023, roughness: 0.42, metalness: 0.55 })
    const mesh = new THREE.InstancedMesh(geo, mat, count)
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    scene.add(mesh)

    const base: { x: number; y: number; z: number; phase: number }[] = []
    const z = new Float32Array(count)
    const vz = new Float32Array(count)
    const colors = new Float32Array(count * 3)
    const w = COLS * (S + G)
    const h = ROWS * (S + G)
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        base.push({ x: c * (S + G) - w / 2 + S / 2, y: r * (S + G) - h / 2 + S / 2, z: Math.random() * 0.35, phase: Math.random() * Math.PI * 2 })
      }
    }
    mesh.instanceColor = new THREE.InstancedBufferAttribute(colors, 3)

    scene.add(new THREE.AmbientLight(0x9fb3bd, 0.35))
    const key = new THREE.DirectionalLight(0xdfe8ec, 1.1)
    key.position.set(-6, 9, 10)
    scene.add(key)
    const rim = new THREE.DirectionalLight(0x2b6f7a, 0.6)
    rim.position.set(8, -6, 6)
    scene.add(rim)
    const cyan = new THREE.PointLight(0x00d9f5, 30, 9, 1.6)
    cyan.position.set(0, 0, 3)
    scene.add(cyan)

    const pointer = new THREE.Vector2(9, 9)
    const target = new THREE.Vector3(999, 999, 0)
    const smooth = new THREE.Vector3(0, 0, 0)
    const ray = new THREE.Raycaster()
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0)
    let active = false

    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) {
        active = false
        return
      }
      pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      ray.setFromCamera(pointer, camera)
      ray.ray.intersectPlane(plane, target)
      active = true
    }
    addEventListener('pointermove', onMove, { passive: true })

    const resize = () => {
      const { width, height } = el.getBoundingClientRect()
      renderer.setSize(width, height, false)
      camera.aspect = width / Math.max(1, height)
      // keep the wall filling the frame at any aspect
      const fitH = h * 0.62
      const fitW = (w * 0.62) / camera.aspect
      const dist = Math.max(fitH, fitW) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)))
      camera.position.z = Math.min(26, Math.max(9, dist + 2))
      camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()

    let visible = true
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting), { threshold: 0 })
    io.observe(el)

    const m4 = new THREE.Matrix4()
    const q = new THREE.Quaternion()
    const e3 = new THREE.Euler()
    const pos = new THREE.Vector3()
    const scl = new THREE.Vector3(1, 1, 1)
    const cA = new THREE.Color(0x161b1e)
    const cB = new THREE.Color(0x0d8fa3)
    const tmp = new THREE.Color()
    let raf = 0
    let t = 0
    let idle = 0

    const frame = () => {
      raf = requestAnimationFrame(frame)
      if (!visible) return
      t += 0.016
      if (!active) {
        // drift the light in a slow figure-eight when nobody is pointing
        idle += 0.006
        target.set(Math.sin(idle * 1.3) * w * 0.28, Math.sin(idle * 2.1) * h * 0.22, 0)
      }
      smooth.lerp(target, 0.08)
      cyan.position.set(smooth.x, smooth.y, 2.6)
      const R = 3.4
      for (let i = 0; i < count; i++) {
        const b = base[i]
        const dx = b.x - smooth.x
        const dy = b.y - smooth.y
        const d = Math.sqrt(dx * dx + dy * dy)
        const f = Math.max(0, 1 - d / R)
        const push = f * f * 1.6
        const wave = still ? 0 : Math.sin(t * 0.8 + b.phase) * 0.06
        const goal = b.z + push + wave
        vz[i] = (vz[i] + (goal - z[i]) * 0.12) * 0.72
        z[i] += vz[i]
        pos.set(b.x, b.y, z[i])
        e3.set(-dy * f * 0.08, dx * f * 0.08, 0)
        q.setFromEuler(e3)
        m4.compose(pos, q, scl)
        mesh.setMatrixAt(i, m4)
        tmp.copy(cA).lerp(cB, f * f * 0.55)
        colors[i * 3] = tmp.r
        colors[i * 3 + 1] = tmp.g
        colors[i * 3 + 2] = tmp.b
      }
      mesh.instanceMatrix.needsUpdate = true
      mesh.instanceColor!.needsUpdate = true
      camera.position.x += (pointer.x * 0.6 - camera.position.x) * 0.03
      camera.lookAt(0, 0, 0)
      renderer.render(scene, camera)
    }
    frame()
    el.classList.add('is-ready')

    return () => {
      cancelAnimationFrame(raf)
      removeEventListener('pointermove', onMove)
      ro.disconnect()
      io.disconnect()
      geo.dispose()
      mat.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [])

  return <div ref={host} className={`cubewall ${className ?? ''}`} />
}
