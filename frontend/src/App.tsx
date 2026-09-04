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

function ProtectedLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader />
      <div className="flex-1">
        <Outlet />
      </div>
      <AppFooter />
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
        <Route path="/research" element={<ResearchPage />} />
        <Route path="/research/:requestId" element={<ResearchProgressPage />} />
        <Route path="/reports/:reportId" element={<ReportReviewPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Route>
      <Route
        path="*"
        element={<Navigate to={session ? '/dashboard' : '/auth'} replace />}
      />
    </Routes>
  )
}
