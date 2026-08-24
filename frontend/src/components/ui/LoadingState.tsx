import { Card } from './Card'
import { IconSpinner } from '../icons'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <Card className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-text-muted">
      <IconSpinner />
      {label}
    </Card>
  )
}
