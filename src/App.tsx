import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { HealthProvider } from './lib/health'
import { SessionProvider } from './lib/session'

const Landing = lazy(() => import('./landing/Landing'))
const ConsoleApp = lazy(() => import('./console/ConsoleApp'))

export default function App() {
  return (
    <HealthProvider>
      <SessionProvider>
        <Suspense fallback={<div className="route-fallback" aria-busy="true" />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/console/*" element={<ConsoleApp />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </SessionProvider>
    </HealthProvider>
  )
}
