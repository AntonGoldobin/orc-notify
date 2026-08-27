import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { me, logout as apiLogout } from '../api/auth'
import type { UserOut } from '../api/types'

export type AuthStatus = 'loading' | 'anon' | 'authed'

export interface AuthContextValue {
  user: UserOut | null
  status: AuthStatus
  refresh: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  const refresh = async () => {
    setStatus('loading')
    try {
      const u = await me()
      setUser(u)
      setStatus('authed')
    } catch {
      setUser(null)
      setStatus('anon')
    }
  }

  const logout = async () => {
    try {
      await apiLogout()
    } catch {
      // best-effort
    }
    setUser(null)
    setStatus('anon')
  }

  useEffect(() => {
    void refresh()
  }, [])

  const value = useMemo<AuthContextValue>(() => ({ user, status, refresh, logout }), [user, status])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
