import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from './lib/auth'
import AuthPage from './pages/AuthPage'

const SCREENS: { path: string; label: string }[] = [
  { path: '/dashboard', label: 'Dashboard' },
  { path: '/discover', label: 'Company Discovery' },
  { path: '/research', label: 'Research a Company' },
  { path: '/research/:requestId', label: 'Research Progress' },
  { path: '/reports/:reportId', label: 'Report Review' },
  { path: '/history', label: 'History' },
]

function AppHeader() {
  const { session, signOut } = useAuth()
  return (
    <header className="flex h-12 items-center justify-between border-b border-line-soft bg-card px-4 sm:px-6">
      <div className="flex items-center gap-2">
        <svg width="20" height="20" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="6" fill="#0f172a" />
          <g fill="#f8fafc">
            <rect x="9" y="9" width="6" height="6" rx="1" />
            <rect x="17" y="9" width="6" height="6" rx="1" />
            <rect x="9" y="17" width="6" height="6" rx="1" />
            <rect x="17" y="17" width="6" height="6" rx="1" />
          </g>
        </svg>
        <span className="font-display text-sm font-bold tracking-tight text-ink">SalesLens</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden text-sm text-ink-soft sm:block">{session?.user.email}</span>
        <button
          type="button"
          onClick={() => void signOut()}
          className="flex h-8 items-center gap-1.5 rounded-control border border-line px-2.5 font-ui text-[13px] font-medium text-ink transition-colors hover:border-ink-faint hover:bg-canvas"
        >
          <LogOut size={15} />
          Log out
        </button>
      </div>
    </header>
  )
}

function ShellStub({ label }: { label: string }) {
  const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-3xl px-8 py-16">
        <p className="label-caps text-ink-faint">SalesLens shell placeholder</p>
        <h1 className="mt-2 font-display text-3xl font-semibold text-ink">{label}</h1>
        <p className="mt-4 text-sm text-ink-soft">
          This screen is not built yet. The shell routes, auth gate, API client
          (<span className="font-display text-action">{apiUrl}</span>) and design tokens
          are live.
        </p>
      </main>
    </>
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
      {SCREENS.map((screen) => (
        <Route
          key={screen.path}
          path={screen.path}
          element={
            <ProtectedRoute>
              <ShellStub label={screen.label} />
            </ProtectedRoute>
          }
        />
      ))}
      <Route
        path="*"
        element={<Navigate to={session ? '/dashboard' : '/auth'} replace />}
      />
    </Routes>
  )
}
