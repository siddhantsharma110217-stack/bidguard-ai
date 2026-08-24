import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className = '' }: CardProps) {
  return (
    <div
      className={`rounded-md border border-border bg-panel ${className}`}
    >
      {children}
    </div>
  )
}
