import { useState } from 'react'
import { getBidDocuments } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { useEvaluation } from '../context/EvaluationContext'
import { useApi } from '../hooks/useApi'
import { PageHeader } from '../components/ui/PageHeader'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { LoadingState } from '../components/ui/LoadingState'
import { ErrorState } from '../components/ui/ErrorState'
import { EmptyState } from '../components/ui/EmptyState'
import { IconFolder, IconScanLine, IconAlertTriangle } from '../components/icons'
import { UploadBidPanel } from '../components/UploadBidPanel'
import { formatBytes } from '../extraction'

export function DocumentsPage() {
  const { selectedBidId: bidId, loading: demoLoading, loadDemo } = useDemo()
  const [showUpload, setShowUpload] = useState(false)

  const { data, loading, error, reload } = useApi(
    () => getBidDocuments(bidId as number),
    [bidId],
    bidId != null,
  )

  // Missing-evidence callout is derived from the shared evaluation context.
  const { results: evaluation } = useEvaluation()
  const missing = evaluation
    ? evaluation.results.filter((res) => res.verdict === 'MISSING')
    : null

  const uploadAction =
    bidId != null ? (
      <button
        onClick={() => setShowUpload((v) => !v)}
        className="rounded border border-accent-border bg-accent-bg px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent-bg/80"
      >
        {showUpload ? 'Hide upload' : 'Upload bid'}
      </button>
    ) : undefined

  // The header and upload panel stay mounted while the body below switches
  // between loading / error / data, so switching to a freshly uploaded bid
  // does not discard the panel's confirmation message.
  let body
  if (!demoLoading && bidId == null) {
    body = (
      <EmptyState
        icon={IconFolder}
        title="No bid loaded"
        description="Load the sample bidder document package to review it here."
        actionLabel="Load Demo"
        onAction={loadDemo}
        actionLoading={demoLoading}
      />
    )
  } else if (loading || demoLoading) {
    body = <LoadingState label="Loading documents…" />
  } else if (error || !data) {
    body = <ErrorState message={error ?? 'Documents could not be loaded.'} onRetry={reload} />
  } else {
    body = (
      <>
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-text-faint">Bidder</div>
            <div className="mt-2 text-sm font-semibold text-text">{data.bid.bidder_name}</div>
          </Card>
          <Card className="p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
              Documents Submitted
            </div>
            <div className="mt-2 text-2xl font-semibold tabular-nums text-text">{data.total}</div>
          </Card>
          <Card className="p-4">
            <div className="text-xs font-medium uppercase tracking-wide text-text-faint">
              Bid Status
            </div>
            <div className="mt-2 text-sm font-semibold text-text">{data.bid.status}</div>
          </Card>
        </div>

        {/* `?? []`: tolerate a backend deployed before contact details existed. */}
        {(data.contact ?? []).length > 0 && (
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold text-text">Bidder Contact Details</h2>
            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {(data.contact ?? []).map((c) => (
                <div key={c.field}>
                  <dt className="text-xs text-text-faint">{c.label}</dt>
                  <dd className="mt-0.5 text-sm font-medium text-text">{c.value}</dd>
                  <dd className="mt-0.5 text-xs text-text-faint">
                    {c.source_document}
                    {c.source_page > 0 && `, page ${c.source_page}`}
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        )}

        <Card className="overflow-x-auto">
          <table className="w-full min-w-[1100px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-text-faint">
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Classification</th>
                <th className="px-4 py-3">Pages</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Text Layer</th>
                <th className="px-4 py-3">Extraction</th>
                <th className="px-4 py-3">Fields Extracted</th>
                <th className="px-4 py-3">SHA-256 Fingerprint</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((doc) => (
                <tr key={doc.id} className="border-b border-border last:border-0 hover:bg-panel-raised">
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">{doc.original_filename}</div>
                    <div className="text-xs text-text-faint">
                      {doc.source === 'UPLOAD' ? 'Uploaded PDF' : 'Sample data'}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-muted">{doc.doc_type.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-3 text-text-muted">
                    {doc.classified_by} · {Math.round(doc.doc_type_confidence * 100)}%
                  </td>
                  <td className="px-4 py-3 tabular-nums text-text-muted">{doc.page_count}</td>
                  <td className="px-4 py-3 tabular-nums text-text-muted">
                    {doc.file_size ? formatBytes(doc.file_size) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {doc.has_text_layer ? (
                      <Badge tone="pass">Text layer present</Badge>
                    ) : (
                      <Badge tone="review">
                        <IconScanLine width={12} height={12} />
                        Scanned — flagged for review
                      </Badge>
                    )}
                    {doc.text_status && (
                      <div className="mt-1 max-w-[14rem] text-xs text-review">{doc.text_status}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <div className={doc.extraction_mode === 'AI' ? 'text-accent' : 'text-text-muted'}>
                      {doc.extraction_label || 'Pre-extracted sample data'}
                    </div>
                    {doc.extraction_note && (
                      <div className="mt-0.5 max-w-[14rem] text-text-faint">{doc.extraction_note}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-muted tabular-nums">{doc.extracted_field_count}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-text-faint" title={doc.sha256}>
                    {doc.sha256 ? `${doc.sha256.slice(0, 16)}…` : 'Not recorded'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {missing && missing.length > 0 && (
          <Card className="border-missing/30 p-5">
            <div className="mb-2 flex items-center gap-2">
              <IconAlertTriangle width={16} height={16} className="text-missing" />
              <h2 className="text-sm font-semibold text-text">Missing Evidence</h2>
            </div>
            <p className="text-sm text-text-muted">
              The following requirements have no corresponding document in this package:
            </p>
            <ul className="mt-2 space-y-1">
              {missing.map((r) => (
                <li key={r.requirement_code} className="flex items-center gap-2 text-sm">
                  <Badge tone="missing">{r.requirement_code}</Badge>
                  <span className="text-text">{r.requirement_title}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Bidder Documents"
        description={
          data && !loading
            ? `${data.bid.bidder_name} — ${data.tender.title}`
            : 'Documents submitted with the bid.'
        }
        actions={uploadAction}
      />
      {showUpload && <UploadBidPanel onClose={() => setShowUpload(false)} />}
      {body}
    </div>
  )
}
