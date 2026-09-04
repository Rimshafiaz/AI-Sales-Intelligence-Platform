import { Check } from 'lucide-react'
import {
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from 'react'

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
        {code && <span className="font-ui text-[11px] font-medium uppercase">{code}</span>}
        <p className={code ? 'mt-0.5' : ''}>{children}</p>
      </div>
    </div>
  )
}

export function StatusBadge({ status }: { status: 'draft' | 'approved' }) {
  return status === 'approved' ? (
    <span className="inline-flex items-center gap-1 rounded-control border border-forest bg-forest-wash px-1.5 py-0.5 font-ui text-[11px] font-medium text-ok-ink">
      <Check size={12} />
      Approved
    </span>
  ) : (
    <span className="inline-flex items-center rounded-control border border-warn-bg bg-warn-bg px-1.5 py-0.5 font-ui text-[11px] font-medium text-warn-ink">
      Draft
    </span>
  )
}

export function RecommendationBadge({ recommendation }: { recommendation: string }) {
  const styles: Record<string, string> = {
    prioritize: 'border-forest bg-forest-wash text-ok-ink',
    consider: 'border-warn-bg bg-warn-bg text-warn-ink',
    do_not_prioritize: 'border-line bg-slate-wash text-ink-soft',
  }
  const label: Record<string, string> = {
    prioritize: 'Prioritize',
    consider: 'Consider',
    do_not_prioritize: 'Do not prioritize',
  }
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 rounded-control border px-1.5 py-0.5 font-ui text-[11px] font-medium ' +
        (styles[recommendation] ?? styles.consider)
      }
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label[recommendation] ?? recommendation}
    </span>
  )
}

interface TextareaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  hint?: string
}

export function TextareaField({
  label,
  hint,
  className = '',
  ...props
}: TextareaFieldProps) {
  const id = useId()
  return (
    <label htmlFor={id} className="block">
      <span className="flex items-baseline justify-between">
        <span className="font-ui text-[13px] font-medium text-ink-soft">{label}</span>
        {hint && <span className="font-ui text-[11px] text-ink-faint">{hint}</span>}
      </span>
      <textarea
        id={id}
        rows={4}
        className={
          'mt-1.5 block w-full rounded-control border border-line bg-card px-3 py-2 ' +
          'font-ui text-sm text-ink placeholder:text-ink-faint ' +
          'focus:border-ink focus:outline focus:outline-1 focus:outline-action ' +
          className
        }
        {...props}
      />
    </label>
  )
}
