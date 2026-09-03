import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CircleAlert, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { useAuth } from '../lib/auth'

type Mode = 'signin' | 'signup'
type Notice = { kind: 'error' | 'info'; code: string | null; message: string }

const inputClass =
  'h-10 w-full rounded-lg border border-line-soft bg-card px-3 font-narrative text-sm text-ink ' +
  'shadow-sm outline-none transition-all placeholder:text-ink-faint focus:bg-slate-wash ' +
  'focus:border-line'

export default function AuthPage() {
  const { signIn, signUp } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function switchMode(next: Mode) {
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

  const tabBase =
    'flex-1 px-3 py-1.5 rounded-control font-ui text-[13px] text-center transition-all duration-150'

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-4 py-12">
      <div className="w-full max-w-md">
        <div className="relative flex flex-col gap-6 rounded-card border border-line-soft bg-card p-8 shadow-sm">
          <div className="flex flex-col items-center gap-1 text-center">
            <div className="flex h-8 items-center justify-center gap-2">
              <svg width="24" height="24" viewBox="0 0 32 32" aria-hidden="true">
                <rect width="32" height="32" rx="6" fill="#0f172a" />
                <g fill="#f8fafc">
                  <rect x="9" y="9" width="6" height="6" rx="1" />
                  <rect x="17" y="9" width="6" height="6" rx="1" />
                  <rect x="9" y="17" width="6" height="6" rx="1" />
                  <rect x="17" y="17" width="6" height="6" rx="1" />
                </g>
              </svg>
              <span className="font-display text-lg font-bold tracking-tight text-ink">
                SalesLens
              </span>
            </div>
            <p className="font-ui text-[11px] uppercase tracking-wider text-ink-soft">
              Sales intelligence workspace
            </p>
          </div>

          <div
            aria-label="Authentication mode"
            role="tablist"
            className="flex items-center gap-0.5 rounded-lg bg-slate-wash p-0.5"
          >
            {(['signin', 'signup'] as Mode[]).map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={mode === value}
                onClick={() => switchMode(value)}
                className={
                  tabBase +
                  (mode === value
                    ? ' bg-card font-semibold text-ink shadow-sm'
                    : ' font-medium text-ink-soft hover:text-ink')
                }
              >
                {value === 'signin' ? 'Sign in' : 'Sign up'}
              </button>
            ))}
          </div>

          {notice && (
            <div
              role="alert"
              className={
                'flex items-start gap-2 rounded-lg p-3 ' +
                (notice.kind === 'error'
                  ? 'bg-bad-bg/40 text-bad-ink'
                  : 'bg-slate-wash text-ink-soft')
              }
            >
              {notice.kind === 'error' && (
                <CircleAlert size={18} className="mt-px shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 flex items-center justify-between gap-2">
                  <span className="font-ui text-[11px] font-semibold uppercase">
                    {notice.kind === 'error' ? 'Authentication error' : 'Confirmation required'}
                  </span>
                  {notice.code && (
                    <span className="font-mono text-[10px] uppercase">{notice.code}</span>
                  )}
                </div>
                <p className="text-[13px] font-medium leading-tight">{notice.message}</p>
              </div>
            </div>
          )}

          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="email"
                className="flex items-center justify-between font-ui text-[13px] font-medium text-ink-soft"
              >
                <span>Email</span>
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
                className={inputClass}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="font-ui text-[13px] font-medium text-ink-soft"
                >
                  Password
                </label>
                {mode === 'signup' && (
                  <span className="font-ui text-[11px] text-ink-faint">
                    Minimum 8 characters
                  </span>
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
                  className={inputClass + ' pr-10'}
                />
                <button
                  type="button"
                  aria-label="Toggle password visibility"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute right-0 flex h-10 w-10 items-center justify-center text-ink-faint transition-colors hover:text-ink"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="mt-1 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-ink font-ui text-sm font-semibold text-canvas shadow-sm transition-all duration-150 hover:bg-ink-soft active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
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
              onClick={() => switchMode(mode === 'signin' ? 'signup' : 'signin')}
              className="text-[13px] text-ink-soft transition-colors hover:text-ink"
            >
              {mode === 'signin' ? "Don't have an account? " : 'Already have credentials? '}
              <span className="font-semibold text-ink underline underline-offset-4">
                {mode === 'signin' ? 'Sign up' : 'Sign in'}
              </span>
            </button>
          </div>

          <div className="mt-1 flex items-start gap-2 rounded-lg bg-slate-wash p-3">
            <ShieldCheck size={16} className="mt-0.5 shrink-0 text-ink-faint" />
            <p className="text-[11px] leading-relaxed text-ink-soft">
              SalesLens is an evidence-backed intelligence platform. Outreach is
              never automatically sent.
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
