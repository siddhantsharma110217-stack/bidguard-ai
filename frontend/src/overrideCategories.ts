/** Officer override reason categories. Codes match the backend's
 *  `app.audit.REASON_CATEGORIES`; the placeholder prompts for the reference
 *  that category usually comes with. */
export interface ReasonCategory {
  code: string
  label: string
  placeholder: string
}

export const REASON_CATEGORIES: ReasonCategory[] = [
  {
    code: 'BIDDER_CLARIFICATION',
    label: 'Clarification received from bidder',
    placeholder:
      'e.g. Bidder letter no. TN/2026/118 dated 12-03-2026 confirms delivery within 30 days',
  },
  {
    code: 'EVIDENCE_ELSEWHERE',
    label: 'Evidence found elsewhere in the bid',
    placeholder: 'e.g. Valid BIS certificate found in Annexure_B.pdf, page 4',
  },
  {
    code: 'EXTRACTION_ERROR',
    label: 'System extraction error',
    placeholder: 'e.g. Commercial_Bid.pdf page 3 states 30 days; system read it as 45',
  },
  {
    code: 'TENDER_CORRIGENDUM',
    label: 'Tender corrigendum or amendment',
    placeholder: 'e.g. Corrigendum no. 2 dated 05-03-2026 relaxed delivery period to 45 days',
  },
  {
    code: 'COMMITTEE_DECISION',
    label: 'Committee decision',
    placeholder: 'e.g. Technical evaluation committee meeting TEC/2026/07, item 3, dated 14-03-2026',
  },
  {
    code: 'OTHER',
    label: 'Other',
    placeholder: 'Describe the reason and cite the letter, document and page, or meeting reference',
  },
]

export const NOT_SPECIFIED = 'Not specified'

/** Label for a stored code; overrides made before categories existed have none. */
export function categoryLabel(code: string | null | undefined): string {
  return REASON_CATEGORIES.find((c) => c.code === code)?.label ?? NOT_SPECIFIED
}
