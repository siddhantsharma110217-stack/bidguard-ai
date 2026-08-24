import { NavLink } from 'react-router-dom'
import type { ComponentType, SVGProps } from 'react'
import {
  IconGrid,
  IconFileText,
  IconListChecks,
  IconFolder,
  IconActivity,
  IconShieldCheck,
  IconBarChart,
} from '../icons'

interface NavItem {
  label: string
  to: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: IconGrid },
  { label: 'Tender', to: '/tender', icon: IconFileText },
  { label: 'Requirements', to: '/requirements', icon: IconListChecks },
  { label: 'Documents', to: '/documents', icon: IconFolder },
  { label: 'Evaluation', to: '/evaluation', icon: IconActivity },
  { label: 'Compliance', to: '/compliance', icon: IconShieldCheck },
  { label: 'Reports', to: '/reports', icon: IconBarChart },
]

export function Sidebar() {
  return (
    <aside className="no-print flex w-60 shrink-0 flex-col border-r border-border bg-panel">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded border border-accent-border bg-accent-bg text-accent">
          <IconShieldCheck width={16} height={16} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-text">BidGuard AI</div>
          <div className="text-[11px] text-text-faint">GeM Compliance Platform</div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 p-3">
        {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-accent-bg text-accent font-medium border border-accent-border'
                  : 'border border-transparent text-text-muted hover:bg-panel-raised hover:text-text'
              }`
            }
          >
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3 text-[11px] text-text-faint">
        SIH26100 — Prototype build
      </div>
    </aside>
  )
}
