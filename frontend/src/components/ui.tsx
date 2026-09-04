import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-ink text-canvas hover:bg-ink-soft',
  secondary:
    'border border-line bg-card text-ink hover:border-ink-faint hover:bg-canvas',
}

export function Button({ variant = 'primary', className = '', children, ...props }: ButtonProps) {
  return (
    <button
      className={
        'inline-flex h-9 items-center justify-center gap-2 rounded-control px-3 ' +
        'font-ui text-sm font-semibold transition-colors ' +
        'disabled:cursor-not-allowed disabled:opacity-60 ' +
        BUTTON_VARIANTS[variant] +
        (className ? ` ${className}` : '')
      }
      {...props}
    >
      {children}
    </button>
  )
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
}

export function TextField({ label, hint, className = '', ...props }: TextFieldProps) {
  const id = useId()
  return (
    <label htmlFor={id} className="block">
      <span className="flex items-baseline justify-between">
        <span className="font-ui text-[13px] font-medium text-ink-soft">{label}</span>
        {hint && <span className="font-ui text-[11px] text-ink-faint">{hint}</span>}
      </span>
      <input
        id={id}
        name={id}
        className={
          'mt-1.5 block h-9 w-full rounded-control border border-line bg-card px-3 ' +
          'font-ui text-sm text-ink placeholder:text-ink-faint ' +
          'focus:border-ink focus:outline focus:outline-1 focus:outline-action ' +
          className
        }
        {...props}
      />
    </label>
  )
}

export function Notice({
  kind,
  code,
  children,
}: {
  kind: 'error' | 'info'
  code?: string | null
  children: ReactNode
}) {
  return (
    <div
      role="status"
      className={
        'flex items-start gap-2 rounded-control p-3 text-sm ' +
        (kind === 'error'
          ? 'bg-bad-bg/60 text-bad-ink'
          : 'bg-slate-wash text-ink-soft')
      }
    >
      <div className="min-w-0 flex-1">
        {code && <span className="font-display text-[11px] font-semibold uppercase">{code}</span>}
        <p className={code ? 'mt-0.5' : ''}>{children}</p>
      </div>
    </div>
  )
}
