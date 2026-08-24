interface StatTileProps {
  label: string
  value: string
  hint?: string
}

export function StatTile({ label, value, hint }: StatTileProps) {
  return (
    <div className="rounded-md border border-border bg-panel p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-text">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-text-muted">{hint}</div>}
    </div>
  )
}
