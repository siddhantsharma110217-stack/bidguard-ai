import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/auth'
import { LoadingState } from './ui/LoadingState'

/** Renders its children only for a logged-in user; otherwise goes to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, checking } = useAuth()
  const location = useLocation()

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center bg-canvas">
        <LoadingState label="Checking your session…" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}
