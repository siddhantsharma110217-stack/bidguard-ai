import type { EvaluationResult } from '../types'
import { citationLabel, extractionMethodLabel } from '../extraction'
import { Badge } from './ui/Badge'

/** How one evidence item was obtained, and (AI mode) whether its citation held up. */
export function EvidenceSource({ result }: { result: EvaluationResult }) {
  const citation = citationLabel(result.citation_status ?? '')
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      <Badge tone={result.extraction_method === 'AI' ? 'accent' : 'neutral'}>
        {extractionMethodLabel(result.extraction_method ?? '')}
      </Badge>
      {citation && <Badge tone={citation.tone}>{citation.label}</Badge>}
    </div>
  )
}
