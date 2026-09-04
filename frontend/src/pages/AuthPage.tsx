import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CircleAlert, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { useAuth } from '../lib/auth'

type Mode = 'signin' | 'signup'
type Notice = { kind: 'error' | 'info'; code: string | null; message: string }

export default function AuthPage() {
  const { signIn, signUp } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function setModeAndReset(next: Mode) {
    setMode(next)
    setNotice(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (submitting) return

    if (mode === 'signup' && password.length < 8) {
      setNotice({ kind: 'error', code: null, message: 'Password must be at least 8 characters.' })
      return
    }

    setSubmitting(true)
    setNotice(null)
    try {
      if (mode === 'signin') {
        await signIn(email, password)
        navigate('/dashboard')
      } else {
        const { needsConfirmation } = await signUp(email, password)
        if (needsConfirmation) {
          setNotice({
            kind: 'info',
            code: null,
            message:
              'Account created. Check your email to confirm your address before signing in.',
          })
        } else {
          navigate('/dashboard')
        }
      }
    } catch (error) {
      const err = error as { code?: string; message?: string }
      setNotice({
        kind: 'error',
        code: err.code ?? null,
        message: err.message ?? 'Authentication failed. Please verify your credentials.',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const tabClass = (active: boolean) =>
    'flex-1 px-2 py-1.5 rounded text-center text-label-md transition-all duration-150 ' +
    (active
      ? 'bg-surface-container-lowest font-semibold text-on-surface shadow-sm'
      : 'font-medium text-on-surface-variant hover:text-on-surface')

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface px-4 py-12">
      <div className="w-full max-w-md">
        <div className="relative flex flex-col gap-6 rounded-xl bg-surface-container-lowest p-8 shadow-sm">
          <div className="flex flex-col items-center gap-1 text-center">
            <div className="flex h-8 items-center gap-2">
              <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
                <rect width="32" height="32" rx="6" fill="#000000" />
                <g fill="#f7f9fb">
                  <rect x="9" y="9" width="6" height="6" rx="1" />
                  <rect x="17" y="9" width="6" height="6" rx="1" />
                  <rect x="9" y="17" width="6" height="6" rx="1" />
                  <rect x="17" y="17" width="6" height="6" rx="1" />
                </g>
              </svg>
              <span className="font-display text-lg font-bold tracking-tight text-on-surface">
                SalesLens
              </span>
            </div>
            <p className="text-label-md uppercase tracking-wider text-on-surface-variant">
              Sales intelligence workspace
            </p>
          </div>

          <div
            aria-label="Authentication mode"
            role="tablist"
            className="flex items-center gap-0.5 rounded-lg bg-surface-container-low p-0.5"
          >
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'signin'}
              onClick={() => setModeAndReset('signin')}
              className={tabClass(mode === 'signin')}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'signup'}
              onClick={() => setModeAndReset('signup')}
              className={tabClass(mode === 'signup')}
            >
              Sign up
            </button>
          </div>

          {notice && (
            <div
              role="alert"
              className={
                'flex items-start gap-2 rounded-lg p-3 ' +
                (notice.kind === 'error' ? 'bg-error-container/40' : 'bg-surface-container-low')
              }
            >
              {notice.kind === 'error' && (
                <CircleAlert size={18} className="mt-px shrink-0 text-error" />
              )}
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 flex items-center justify-between gap-2">
                  <span className="text-label-sm font-semibold uppercase text-error">
                    {notice.kind === 'error' ? 'Authentication error' : 'Confirmation required'}
                  </span>
                  {notice.code && (
                    <span className="font-mono text-[10px] text-error">{notice.code}</span>
                  )}
                </div>
                <p className="text-body-sm font-medium leading-tight text-on-surface">
                  {notice.message}
                </p>
              </div>
            </div>
          )}

          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="email"
                className="text-label-md font-medium text-on-surface-variant"
              >
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                placeholder="name@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="h-10 w-full rounded-lg bg-surface-container-lowest px-3 text-body-md text-on-surface shadow-sm outline-none transition-all placeholder:text-outline-variant focus:bg-surface-container-low"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="text-label-md font-medium text-on-surface-variant"
                >
                  Password
                </label>
                {mode === 'signup' && (
                  <span className="text-label-sm text-outline">Minimum 8 characters</span>
                )}
              </div>
              <div className="relative flex items-center">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={mode === 'signup' ? 8 : undefined}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  placeholder="Enter password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-10 w-full rounded-lg bg-surface-container-lowest px-3 pr-10 text-body-md text-on-surface shadow-sm outline-none transition-all placeholder:text-outline-variant focus:bg-surface-container-low"
                />
                <button
                  type="button"
                  aria-label="Toggle password visibility"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute right-0 flex h-10 w-10 items-center justify-center text-outline transition-colors hover:text-on-surface"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-1 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary text-headline-sm text-on-primary shadow-sm transition-all duration-150 hover:bg-inverse-surface active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span>
                {submitting
                  ? mode === 'signin'
                    ? 'Signing in...'
                    : 'Creating account...'
                  : mode === 'signin'
                    ? 'Sign in to workspace'
                    : 'Create platform account'}
              </span>
              {!submitting && <ArrowRight size={18} />}
            </button>
          </form>

          <div className="pt-1 text-center">
            <button
              type="button"
              onClick={() => setModeAndReset(mode === 'signin' ? 'signup' : 'signin')}
              className="text-body-sm text-on-surface-variant transition-colors hover:text-on-surface"
            >
              {mode === 'signin' ? "Don't have an account? " : 'Already have credentials? '}
              <span className="font-semibold text-on-surface underline underline-offset-4">
                {mode === 'signin' ? 'Sign up' : 'Sign in'}
              </span>
            </button>
          </div>

          <div className="mt-1 flex items-start gap-2 rounded-lg bg-surface-container-low p-3">
            <ShieldCheck size={16} className="mt-0.5 shrink-0 text-outline" />
            <p className="text-label-sm leading-relaxed text-on-surface-variant">
              SalesLens is an evidence-backed intelligence platform. Outreach is
              never automatically sent.
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
