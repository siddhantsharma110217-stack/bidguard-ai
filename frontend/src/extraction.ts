import type { BadgeTone } from './components/ui/Badge'
import type { ExtractionMode } from './types'

/** How a piece of evidence was obtained, as shown on each evidence item. */
export function extractionMethodLabel(method: ExtractionMode | ''): string {
  switch (method) {
    case 'AI':
      return 'AI extraction'
    case 'RULES':
      return 'Rule-based extraction'
    case 'RULES_FALLBACK':
      return 'Rule-based extraction (AI fallback)'
    default:
      return 'Pre-extracted sample data'
  }
}

export function citationLabel(status: string): { label: string; tone: BadgeTone } | null {
  switch (status) {
    case 'VERIFIED':
      return { label: 'Citation verified', tone: 'pass' }
    case 'UNSUPPORTED':
      return { label: 'Unsupported citation', tone: 'fail' }
    case 'VALUE_NOT_IN_QUOTE':
      return { label: 'Value not in quote', tone: 'fail' }
    default:
      return null
  }
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}
