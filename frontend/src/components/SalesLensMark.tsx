export function SalesLensMark({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect width="32" height="32" rx="6" fill="var(--color-brand)" />
      <g fill="var(--color-card)">
        <rect x="9" y="9" width="6" height="6" rx="1" />
        <rect x="17" y="9" width="6" height="6" rx="1" />
        <rect x="9" y="17" width="6" height="6" rx="1" />
        <rect x="17" y="17" width="6" height="6" rx="1" />
      </g>
    </svg>
  )
}
