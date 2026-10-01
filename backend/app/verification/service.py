"""Run issuer verification for an evaluation outcome and apply the rule
interaction:

* VERIFIED keeps the rule's verdict.
* UNVERIFIED or VERIFICATION_FAILED turn a PASS into REVIEW.
* An existing FAIL, MISSING or REVIEW is never changed, and verification
  never produces a FAIL by itself.
"""

from app.evaluation.evaluator import EvaluationOutcome
from app.evaluation.scoring import score_for_verdict
from app.verification.adapter import (
    FAILED_LABEL,
    UNVERIFIED,
    VERIFICATION_FAILED,
    Submitted,
    VerificationResult,
    get_adapters,
    not_applicable,
    now_iso,
)

HOLDER_FIELD = "certificate_holder"
UNCONFIRMED_CITATIONS = ("UNSUPPORTED", "VALUE_NOT_IN_QUOTE")


def verify_outcome(req, outcome: EvaluationOutcome, documents: list, bidder_name: str) -> VerificationResult:
    if not getattr(req, "verification_required", False):
        return not_applicable("Verification is not required for this requirement.")
    adapter = next((a for a in get_adapters() if a.can_verify(req)), None)
    if adapter is None:
        return not_applicable("No verification source is available for this requirement.")
    if outcome.verdict == "MISSING" or outcome.source_document_id is None:
        return not_applicable("No certificate was submitted, so there is nothing to verify.")

    doc = next(d for d in documents if d.id == outcome.source_document_id)
    field_name = (req.rule_params or {}).get("field", "")
    data = (doc.fields or {}).get(field_name) or {}

    if data.get("citation_status") in UNCONFIRMED_CITATIONS:
        reason = (
            "The certificate number's citation could not be confirmed in the document, "
            "so it was not checked against the issuer record."
        )
        return VerificationResult(
            status=UNVERIFIED,
            reason=reason,
            clause="the certificate number's citation could not be confirmed in the document",
            source=adapter.source_name,
            checked_at=now_iso(),
        )

    holder_data = (doc.fields or {}).get(HOLDER_FIELD) or {}
    if holder_data.get("value"):
        holder = str(holder_data["value"])
        holder_source = f"{doc.original_filename}, page {holder_data.get('page', 0)}"
    else:
        holder = bidder_name
        holder_source = "Bidder company name (the certificate does not state a holder)"

    return adapter.verify(
        Submitted(
            certificate_number=str(data.get("value", "")) if not data.get("unreadable") else "",
            holder=holder,
            holder_source=holder_source,
            document_id=doc.id,
            document_name=doc.original_filename,
            page=int(data.get("page", 0) or 0),
        )
    )


def apply_verification(outcome: EvaluationOutcome, result: VerificationResult) -> None:
    """Adjust the outcome for an unconfirmed certificate (PASS -> REVIEW only)."""
    outcome.rule_trace["verification_status"] = result.status
    if outcome.verdict != "PASS" or result.status not in (UNVERIFIED, VERIFICATION_FAILED):
        return
    rule_explanation = outcome.explanation
    outcome.rule_trace["rule_verdict"] = "PASS"
    outcome.verdict = "REVIEW"
    outcome.score = score_for_verdict("REVIEW")
    outcome.decision_source = "RULE+VERIFICATION"
    outcome.explanation = (
        f"Evidence meets the requirement, but {result.clause}. Officer review required. "
        f"(Rule check: {rule_explanation})"
    )
    outcome.recommended_action = (
        f"{FAILED_LABEL}. Confirm the certificate details with the issuer before accepting it."
        if result.status == VERIFICATION_FAILED
        else "Officer review required. Confirm the certificate with the issuer; "
        "no matching record is available in the verification source."
    )
