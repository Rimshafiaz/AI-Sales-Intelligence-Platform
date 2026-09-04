import type { ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './lib/auth'
import { AppHeader } from './components/AppHeader'
import { Button } from './components/ui'
import AuthPage from './pages/AuthPage'
import DiscoveryPage from './pages/DiscoveryPage'
import ResearchPage from './pages/ResearchPage'
import ResearchProgressPage from './pages/ResearchProgressPage'
import ReportReviewPage from './pages/ReportReviewPage'

const UNBUILT_SCREENS: { path: string; label: string }[] = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/history', label: 'History' },
]

function DashboardStub() {
  return (
    <main className="mx-auto max-w-3xl px-8 py-16">
      <p className="label-caps text-ink-faint">SalesLens shell placeholder</p>
      <h1 className="mt-2 font-display text-3xl font-semibold text-ink">Dashboard</h1>
      <p className="mt-4 text-sm text-ink-soft">
        The real dashboard is built in Milestone 58. Until then, the two
        workflows are reachable here:
      </p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <Button onClick={() => (window.location.href = '/discover')}>
          Discover companies
        </Button>
        <Button variant="secondary" onClick={() => (window.location.href = '/research')}>
          Research a company
        </Button>
      </div>
    </main>
  )
}

function ShellStub({ label }: { label: string }) {
  const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  return (
    <main className="mx-auto max-w-3xl px-8 py-16">
      <p className="label-caps text-ink-faint">SalesLens shell placeholder</p>
      <h1 className="mt-2 font-display text-3xl font-semibold text-ink">{label}</h1>
      <p className="mt-4 text-sm text-ink-soft">
        This screen is not built yet. The shell routes, auth gate, API client
        (<span className="font-display text-action">{apiUrl}</span>) and design tokens
        are live.
      </p>
    </main>
  )
}

function ProtectedLayout() {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <Outlet />
    </div>
  )
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  if (loading) return null
  if (!session) return <Navigate to="/auth" replace />
  return <>{children}</>
}

export default function App() {
  const { session, loading } = useAuth()

  if (loading) return null

  return (
    <Routes>
      <Route
        path="/auth"
        element={session ? <Navigate to="/dashboard" replace /> : <AuthPage />}
      />
      <Route
        element={
          <ProtectedRoute>
            <ProtectedLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/discover" element={<DiscoveryPage />} />
        <Route path="/dashboard" element={<DashboardStub />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/research/:requestId" element={<ResearchProgressPage />} />
        <Route path="/reports/:reportId" element={<ReportReviewPage />} />
        {UNBUILT_SCREENS.map((screen) => (
          <Route key={screen.path} path={screen.path} element={<ShellStub label={screen.label} />} />
        ))}
      </Route>
      <Route
        path="*"
        element={<Navigate to={session ? '/dashboard' : '/auth'} replace />}
      />
    </Routes>
  )
}
