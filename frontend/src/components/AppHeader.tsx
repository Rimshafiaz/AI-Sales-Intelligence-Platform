import { NavLink } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { SalesLensMark } from './SalesLensMark'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/history', label: 'History' },
  { to: '/prospects', label: 'Prospects' },
]

export function AppHeader() {
  const { session, signOut } = useAuth()

  return (
    <header className="flex h-12 items-center justify-between border-b border-line-soft bg-card px-4 sm:px-6">
      <div className="flex items-center gap-6">
        <NavLink to="/dashboard" className="flex items-center gap-2">
          <SalesLensMark size={20} />
          <span className="font-display text-sm font-bold tracking-tight text-ink">
            SalesLens
          </span>
        </NavLink>
        <nav className="flex items-center gap-1 self-stretch">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                'flex h-12 items-center border-b-2 px-3 font-ui text-sm transition-colors ' +
                (isActive
                  ? 'border-ink font-semibold text-ink'
                  : 'border-transparent text-ink-soft hover:text-ink')
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden text-sm text-ink-soft sm:block">
          {session?.user.email}
        </span>
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
