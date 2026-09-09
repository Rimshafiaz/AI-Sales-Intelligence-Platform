import type { ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './lib/auth'
import { AppHeader } from './components/AppHeader'
import { AppFooter } from './components/AppFooter'
import AuthPage from './pages/AuthPage'
import DashboardPage from './pages/DashboardPage'
import DiscoveryPage from './pages/DiscoveryPage'
import HistoryPage from './pages/HistoryPage'
import ResearchPage from './pages/ResearchPage'
import ResearchProgressPage from './pages/ResearchProgressPage'
import ReportReviewPage from './pages/ReportReviewPage'
import NotFoundPage from './pages/NotFoundPage'
import ProspectsPage from './pages/ProspectsPage'

function IdleWarningBanner() {
  const { idleWarning, staySignedIn } = useAuth()
  if (!idleWarning) return null
  return (
    <div className="fixed bottom-5 right-5 z-50 w-80 rounded-card border border-line bg-surface-container-lowest p-4 shadow-sm">
      <p className="text-body-sm text-on-surface">
        You have been inactive. You will be signed out in 2 minutes.
      </p>
      <button
        type="button"
        onClick={staySignedIn}
        className="mt-3 inline-flex items-center rounded-control bg-primary px-3 py-1.5 text-label-md font-medium text-on-primary transition-colors hover:bg-inverse-surface"
      >
        Stay signed in
      </button>
    </div>
  )
}

function ProtectedLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader />
      <div className="flex-1">
        <Outlet />
      </div>
      <AppFooter />
      <IdleWarningBanner />
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
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/discover" element={<DiscoveryPage />} />
        <Route path="/prospects" element={<ProspectsPage />} />
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/research/:requestId" element={<ResearchProgressPage />} />
        <Route path="/reports/:reportId" element={<ReportReviewPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
