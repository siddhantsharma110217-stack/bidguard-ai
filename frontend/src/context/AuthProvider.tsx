import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getMe, login as loginApi, setAuthToken, setUnauthorizedHandler } from '../api/client'
import type { AuthUser } from '../types'
import { AuthContext } from './auth'

// sessionStorage: the session ends when the tab closes. Storage can be
// unavailable (private mode, blocked site data); then it lives in memory only.
const TOKEN_KEY = 'bidguard.session'

interface StoredSession {
  token: string
  expiresAt: number
}

function readStored(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(TOKEN_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredSession
    return parsed.expiresAt * 1000 > Date.now() ? parsed : null
  } catch {
    return null
  }
}

function writeStored(session: StoredSession | null): void {
  try {
    if (session) sessionStorage.setItem(TOKEN_KEY, JSON.stringify(session))
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // memory-only session
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored] = useState(readStored)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checking, setChecking] = useState(stored !== null)
  const [notice, setNotice] = useState<string | null>(null)

  const logout = useCallback((message?: string) => {
    setAuthToken(null)
    writeStored(null)
    setUser(null)
    setNotice(message ?? null)
  }, [])

  // Any 401 from the API (expired or invalid session) logs out.
  useEffect(() => {
    setUnauthorizedHandler(() => logout('Your session has ended. Please log in again.'))
    return () => setUnauthorizedHandler(null)
  }, [logout])

  // Restore a session saved in this tab, after checking it with the backend.
  useEffect(() => {
    if (!stored) return
    let cancelled = false
    setAuthToken(stored.token)
    getMe()
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) logout()
      })
      .finally(() => {
        if (!cancelled) setChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [stored, logout])

  const login = useCallback(async (username: string, password: string) => {
    const result = await loginApi(username, password)
    setAuthToken(result.token)
    writeStored({ token: result.token, expiresAt: result.expires_at })
    setNotice(null)
    setUser(result.user)
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, checking, notice, isOfficer: user?.role === 'OFFICER', login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}
