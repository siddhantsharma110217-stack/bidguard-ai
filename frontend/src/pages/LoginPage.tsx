import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError, getDemoAccounts } from '../api/client'
import { useAuth } from '../context/auth'
import { useApi } from '../hooks/useApi'
import { Card } from '../components/ui/Card'
import { IconShieldCheck, IconSpinner } from '../components/icons'

export function LoginPage() {
  const { user, login, notice } = useAuth()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  // Listed only when the backend runs in DEMO_MODE (it returns [] otherwise).
  const { data: demoAccounts } = useApi(getDemoAccounts, [])

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (user) return <Navigate to={from === '/login' ? '/' : from} replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) return
    setSubmitting(true)
    setError(null)
    try {
      await login(username.trim(), password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed.')
      setSubmitting(false)
    }
  }

  const inputClass =
    'w-full rounded border border-border-strong bg-panel px-3 py-2 text-sm text-text focus:border-accent focus:outline-none'

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10 text-text">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded border border-accent-border bg-accent-bg text-accent">
            <IconShieldCheck width={18} height={18} />
          </div>
          <div className="leading-tight">
            <div className="text-base font-semibold">BidGuard AI</div>
            <div className="text-xs text-text-faint">Officer login</div>
          </div>
        </div>

        <Card className="p-6">
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            {notice && <p className="text-xs text-review">{notice}</p>}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-text-muted">Username</span>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                className={inputClass}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-text-muted">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className={inputClass}
              />
            </label>
            {error && <p className="text-xs text-fail">{error}</p>}
            <button
              type="submit"
              disabled={submitting || !username.trim() || !password}
              className="inline-flex items-center justify-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-2 text-sm font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-50"
            >
              {submitting && <IconSpinner />}
              {submitting ? 'Logging in…' : 'Log in'}
            </button>
          </form>
        </Card>

        {demoAccounts && demoAccounts.length > 0 && (
          <Card className="mt-4 p-4">
            <div className="text-xs font-semibold text-text">Demo accounts</div>
            <p className="mt-0.5 text-xs text-text-faint">
              Prototype demo mode. Click an account to fill in the form.
            </p>
            <ul className="mt-2 divide-y divide-border">
              {demoAccounts.map((a) => (
                <li key={a.username}>
                  <button
                    type="button"
                    onClick={() => {
                      setUsername(a.username)
                      setPassword(a.demo_password ?? '')
                      setError(null)
                    }}
                    className="flex w-full items-start justify-between gap-3 py-2 text-left text-xs hover:bg-panel-raised"
                  >
                    <span>
                      <span className="font-medium text-text">{a.full_name}</span>
                      <span className="block text-text-faint">
                        {a.designation} · {a.role}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-text-muted">
                      {a.username}
                      {a.demo_password ? ` / ${a.demo_password}` : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}
