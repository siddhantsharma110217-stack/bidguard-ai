import type { ReactNode } from 'react'

export type BadgeTone = 'pass' | 'review' | 'fail' | 'missing' | 'accent' | 'neutral'

const TONE_CLASSES: Record<BadgeTone, string> = {
  pass: 'text-pass bg-pass-bg border-pass/30',
  review: 'text-review bg-review-bg border-review/30',
  fail: 'text-fail bg-fail-bg border-fail/30',
  missing: 'text-missing bg-missing-bg border-missing/30',
  accent: 'text-accent bg-accent-bg border-accent-border',
  neutral: 'text-text-muted bg-panel-raised border-border-strong',
}

interface BadgeProps {
  tone?: BadgeTone
  children: ReactNode
}

export function Badge({ tone = 'neutral', children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  )
}
