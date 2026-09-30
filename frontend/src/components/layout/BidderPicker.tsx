import { useDemo } from '../../context/DemoContext'

/** Global bidder selector. Switching here re-scopes every bid-level page
 *  (Documents, Evaluation, Compliance, Reports) to the chosen bidder. */
export function BidderPicker() {
  const { bids, selectedBidId, selectBid } = useDemo()

  if (bids.length === 0 || selectedBidId == null) return null

  return (
    <label className="flex items-center gap-2 text-xs text-text-muted">
      <span className="font-medium uppercase tracking-wide text-text-faint">Bidder</span>
      <select
        value={selectedBidId}
        onChange={(e) => selectBid(Number(e.target.value))}
        className="max-w-[18rem] truncate rounded border border-border-strong bg-panel px-2 py-1 text-sm text-text focus:border-accent focus:outline-none"
      >
        {bids.map((bid) => (
          <option key={bid.id} value={bid.id}>
            {bid.bidder_name}
            {bid.status === 'EVALUATED' ? ` — ${bid.compliance_score}%` : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
