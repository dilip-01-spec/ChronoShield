import { useEffect, useLayoutEffect } from 'react'
import Lenis from 'lenis'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import '../styles/landing.css'
import { Cursor, Grain, Preloader, ScrollProgress, finePointer, reducedMotion } from './fx'
import { Hero, Nav } from './Hero'
import Problem from './Problem'
import Journey from './Journey'
import LiveDemo from './LiveDemo'
import TwoStages from './TwoStages'
import { Different, Expansion, Roadmap, Team } from './More'
import FinalCta from './FinalCta'
import Footer from './Footer'

gsap.registerPlugin(ScrollTrigger)

export default function Landing() {
  useEffect(() => {
    document.title = 'ChronoShield — policy before action'
  }, [])

  // Smooth scroll on desktop only, synced with ScrollTrigger through the gsap ticker.
  useEffect(() => {
    if (!finePointer() || reducedMotion()) return
    const lenis = new Lenis({ lerp: 0.1, smoothWheel: true })
    ;(window as unknown as { __lenis?: Lenis }).__lenis = lenis
    lenis.on('scroll', ScrollTrigger.update)
    const tick = (time: number) => lenis.raf(time * 1000)
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)
    return () => {
      gsap.ticker.remove(tick)
      lenis.destroy()
      delete (window as unknown as { __lenis?: Lenis }).__lenis
    }
  }, [])

  // Every [data-reveal] element rises in once, staggered per batch of elements entering together.
  // IntersectionObserver (not scroll math) so jumps, anchor links and pins can never strand content hidden.
  useLayoutEffect(() => {
    if (reducedMotion()) return
    const els = gsap.utils.toArray<HTMLElement>('[data-reveal]')
    gsap.set(els, { opacity: 0, y: 28, filter: 'blur(4px)' })
    const io = new IntersectionObserver(
      (entries) => {
        const entering = entries.filter((e) => e.isIntersecting).map((e) => e.target as HTMLElement)
        if (!entering.length) return
        entering.forEach((el) => io.unobserve(el))
        gsap.to(entering, { opacity: 1, y: 0, filter: 'blur(0px)', duration: 0.9, ease: 'expo.out', stagger: 0.08, overwrite: true, clearProps: 'filter' })
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.01 },
    )
    els.forEach((el) => io.observe(el))
    const refresh = window.setTimeout(() => ScrollTrigger.refresh(), 600)
    return () => {
      window.clearTimeout(refresh)
      io.disconnect()
      gsap.set(els, { clearProps: 'all' })
    }
  }, [])

  return (
    <div className="landing">
      <Preloader />
      <Grain />
      <ScrollProgress />
      <Cursor />
      <a href="#problem" className="skip">
        Skip to content
      </a>
      <Nav />
      <main className="landing-main">
        <Hero />
        <Problem />
        <Journey />
        <LiveDemo />
        <TwoStages />
        <Different />
        <Roadmap />
        <Expansion />
        <Team />
        <FinalCta />
      </main>
      <Footer />
    </div>
  )
}
