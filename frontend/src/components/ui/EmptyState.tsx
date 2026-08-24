import type { ComponentType, ReactNode, SVGProps } from 'react'
import { Card } from './Card'
import { IconSpinner } from '../icons'

interface EmptyStateProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  actionLoading?: boolean
  children?: ReactNode
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionLoading,
  children,
}: EmptyStateProps) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-16 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-border bg-panel-raised text-text-faint">
        <Icon width={20} height={20} />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        <p className="mt-1 max-w-md text-sm text-text-muted">{description}</p>
      </div>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          disabled={actionLoading}
          className="mt-1 inline-flex items-center gap-2 rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80 disabled:opacity-60"
        >
          {actionLoading && <IconSpinner />}
          {actionLabel}
        </button>
      )}
      {children}
    </Card>
  )
}
