import { createContext, useContext } from 'react'
import type { AuthUser } from '../types'

export interface AuthContextValue {
  user: AuthUser | null
  /** A stored session is being checked with the backend. */
  checking: boolean
  /** Shown on the login page, e.g. after a session expired. */
  notice: string | null
  isOfficer: boolean
  login: (username: string, password: string) => Promise<void>
  logout: (notice?: string) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth() must be used inside <AuthProvider>')
  return ctx
}
