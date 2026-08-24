import { Card } from './Card'
import { IconAlertTriangle } from '../icons'

interface ErrorStateProps {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <Card className="flex flex-col items-center gap-3 border-fail/30 px-6 py-12 text-center">
      <IconAlertTriangle className="text-fail" width={22} height={22} />
      <p className="max-w-md text-sm text-text-muted">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded border border-border-strong px-3 py-1.5 text-xs font-medium text-text hover:bg-panel-raised"
        >
          Retry
        </button>
      )}
    </Card>
  )
}
