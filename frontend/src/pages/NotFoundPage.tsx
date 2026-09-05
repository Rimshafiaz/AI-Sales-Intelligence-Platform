import { useNavigate } from 'react-router-dom'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <main className="mx-auto flex min-h-[70vh] w-full max-w-7xl items-center px-4 py-16 sm:px-6">
      <div className="flex w-full flex-col items-start gap-8 sm:flex-row sm:items-center">
        <span className="font-display text-[64px] font-semibold leading-none tracking-tight text-on-surface sm:pr-16 sm:text-[96px]">
          404
        </span>
        <div className="border-line-soft sm:border-l sm:pl-16">
          <p className="label-caps text-ink-faint">Error</p>
          <h1 className="mt-1 font-display text-headline-lg font-semibold tracking-tight text-on-surface">
            Page not found
          </h1>
          <p className="mt-2 max-w-md text-body-md text-on-surface-variant">
            The page you are looking for does not exist or may have moved.
          </p>
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="mt-6 inline-flex items-center gap-2 rounded-control bg-primary px-4 py-2 text-label-md font-medium text-on-primary transition-colors hover:bg-inverse-surface"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    </main>
  )
}
