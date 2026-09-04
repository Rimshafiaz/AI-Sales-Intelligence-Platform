import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'

export const IDLE_LOGOUT_FLAG = 'saleslens:idle-logout'

const IDLE_TIMEOUT_MS = 30 * 60 * 1000
const IDLE_WARN_BEFORE_MS = 2 * 60 * 1000
const IDLE_CHECK_INTERVAL_MS = 15 * 1000

interface AuthState {
  session: Session | null
  loading: boolean
  idleWarning: boolean
  staySignedIn: () => void
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [idleWarning, setIdleWarning] = useState(false)
  const lastActivityRef = useRef(Date.now())

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) {
      setIdleWarning(false)
      return
    }

    const markActivity = () => {
      lastActivityRef.current = Date.now()
    }
    const activityEvents = ['pointermove', 'keydown', 'click', 'scroll', 'touchstart']
    activityEvents.forEach((eventName) =>
      window.addEventListener(eventName, markActivity, { passive: true }),
    )

    const interval = window.setInterval(() => {
      const idleFor = Date.now() - lastActivityRef.current
      if (idleFor >= IDLE_TIMEOUT_MS) {
        sessionStorage.setItem(IDLE_LOGOUT_FLAG, '1')
        void supabase.auth.signOut()
      } else {
        setIdleWarning(idleFor >= IDLE_TIMEOUT_MS - IDLE_WARN_BEFORE_MS)
      }
    }, IDLE_CHECK_INTERVAL_MS)

    return () => {
      activityEvents.forEach((eventName) =>
        window.removeEventListener(eventName, markActivity),
      )
      window.clearInterval(interval)
    }
  }, [session])

  const value: AuthState = {
    session,
    loading,
    idleWarning,
    staySignedIn: () => {
      lastActivityRef.current = Date.now()
      setIdleWarning(false)
    },
    signUp: async (email, password) => {
      const { data, error } = await supabase.auth.signUp({ email, password })
      if (error) throw error
      return { needsConfirmation: data.session === null }
    },
    signIn: async (email, password) => {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
    },
    signOut: async () => {
      await supabase.auth.signOut()
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
