// Minimal hand-rolled icon set (stroke-based, currentColor) — avoids pulling
// in an icon library for a handful of static nav glyphs.
import type { SVGProps } from 'react'

function Base(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={18}
      height={18}
      {...props}
    />
  )
}

export function IconGrid(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </Base>
  )
}

export function IconFileText(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </Base>
  )
}

export function IconListChecks(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="m3 6 1.5 1.5L7.5 4.5" />
      <path d="m3 13 1.5 1.5 3-3" />
      <path d="M11 6h10M11 13h10M11 20h10" />
      <path d="m3 20 1.5 1.5 3-3" />
    </Base>
  )
}

export function IconFolder(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </Base>
  )
}

export function IconActivity(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </Base>
  )
}

export function IconShieldCheck(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </Base>
  )
}

export function IconBarChart(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M4 20V10M12 20V4M20 20v-7" />
    </Base>
  )
}

export function IconDot(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 8 8" width={8} height={8} {...props}>
      <circle cx="4" cy="4" r="4" fill="currentColor" />
    </svg>
  )
}

export function IconSpinner(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      width={16}
      height={16}
      className="animate-spin"
      {...props}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export function IconAlertTriangle(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="m10.29 3.86-8.18 14A2 2 0 0 0 3.82 21h16.36a2 2 0 0 0 1.71-3.14l-8.18-14a2 2 0 0 0-3.42 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </Base>
  )
}

export function IconScanLine(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" />
      <path d="M3 12h18" />
    </Base>
  )
}
