"""Evaluation endpoints.

A bid has exactly one current evaluation, so the bid id doubles as the
evaluation id — `POST /api/evaluations` runs (or re-runs) the evaluation for
a bid and returns results keyed by that id.

Officers can override any verdict via `POST /api/evaluations/{bid_id}/overrides`.
The system's verdict is never overwritten; the officer's verdict becomes the
effective one, and every override is written to the hash-chained audit log.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.bids import get_bid_or_404
from app.audit import REASON_CATEGORIES, append_event, utc_timestamp
from app.auth import current_user, require_officer
from app.db import get_db
from app.evaluation.evaluator import get_evaluator
from app.evaluation.scoring import VERDICTS, compute_summary, score_for_verdict
from app.verification.adapter import NOT_APPLICABLE
from app.verification.service import apply_verification, verify_outcome
from app.models import Bid, Document, Evaluation, Evidence, Requirement, User
from app.schemas import (
    BidOut,
    EvaluationCreate,
    EvaluationResultsOut,
    OverrideCreate,
    ResultOut,
    SummaryOut,
    TenderOut,
)

router = APIRouter(
    prefix="/api/evaluations", tags=["evaluations"], dependencies=[Depends(current_user)]
)

MIN_REASON_LENGTH = 15


def _effective_verdict(row: Evaluation) -> str:
    return row.officer_verdict or row.verdict


def _effective_score(row: Evaluation) -> float:
    return score_for_verdict(row.officer_verdict) if row.officer_verdict else row.score


def _apply_summary_to_bid(bid: Bid, rows: list[Evaluation]) -> None:
    summary = compute_summary(
        [
            SimpleNamespace(
                verdict=_effective_verdict(r),
                score=_effective_score(r),
                obligation=r.requirement.obligation,
            )
            for r in rows
        ]
    )
    bid.compliance_score = summary["overall_compliance"]
    bid.risk_score = summary["risk_score"]
    bid.risk_band = summary["risk_band"]
    bid.gate_status = summary["gate_status"]


def _run_evaluation(bid_id: int, db: Session, user: User | None = None) -> None:
    """Evaluate every requirement for the bid and persist the results.

    Requirements marked `verification_required` are also checked against the
    issuer's record; each check is written to the audit log with the user
    who ran the evaluation.
    """
    bid = get_bid_or_404(bid_id, db)

    requirements = (
        db.query(Requirement)
        .filter(Requirement.tender_id == bid.tender_id)
        .order_by(Requirement.code)
        .all()
    )
    if not requirements:
        raise HTTPException(
            status_code=409,
            detail="This tender has no requirements to evaluate against.",
        )

    documents = db.query(Document).filter(Document.bid_id == bid_id).all()
    if not documents:
        raise HTTPException(
            status_code=409,
            detail=(
                "This bid has no submitted documents. Upload or load a bidder "
                "document package before running an evaluation."
            ),
        )

    # Clear any previous run so re-evaluating is idempotent. Officer
    # overrides are decisions, not system output, so they carry over.
    prior = db.query(Evaluation).filter(Evaluation.bid_id == bid_id).all()
    carried_overrides = {
        row.requirement_id: (
            row.officer_verdict,
            row.override_reason,
            row.override_category,
            row.officer_name,
            row.officer_username,
            row.overridden_at,
        )
        for row in prior
        if row.officer_verdict
    }
    for row in prior:
        db.delete(row)
    db.flush()

    bid.status = "EVALUATING"
    db.flush()

    outcomes = get_evaluator().evaluate_bid(requirements, documents)
    if not outcomes:
        bid.status = "FAILED"
        db.commit()
        raise HTTPException(
            status_code=500, detail="The evaluation produced no results."
        )

    req_by_id = {r.id: r for r in requirements}
    checks = []
    for out in outcomes:
        req = req_by_id[out.requirement_id]
        check = verify_outcome(req, out, documents, bid.bidder_name)
        apply_verification(out, check)
        checks.append(check)

    rows: list[Evaluation] = []
    for out, check in zip(outcomes, checks):
        row = Evaluation(
            verification_status=check.status,
            verification_reason=check.reason,
            verification_source=check.source,
            verification_checked_at=check.checked_at,
            verification_document_id=(
                out.source_document_id if check.status != NOT_APPLICABLE else None
            ),
            verification_details=check.details(),
            bid_id=bid_id,
            requirement_id=out.requirement_id,
            verdict=out.verdict,
            score=out.score,
            confidence=out.confidence,
            decision_source=out.decision_source,
            rule_trace=out.rule_trace,
            explanation=out.explanation,
            recommended_action=out.recommended_action,
        )
        override = carried_overrides.get(out.requirement_id)
        if override and override[0] != out.verdict:
            (
                row.officer_verdict,
                row.override_reason,
                row.override_category,
                row.officer_name,
                row.officer_username,
                row.overridden_at,
            ) = override
        db.add(row)
        db.flush()
        rows.append(row)

        if check.status != NOT_APPLICABLE:
            doc = next(d for d in documents if d.id == out.source_document_id)
            req = req_by_id[out.requirement_id]
            append_event(
                db,
                "DOCUMENT_VERIFICATION",
                timestamp=check.checked_at,
                bid_id=bid.id,
                bidder_name=bid.bidder_name,
                requirement_id=req.id,
                requirement_code=req.code,
                requirement_title=req.title,
                document_id=doc.id,
                document_name=doc.original_filename,
                document_sha256=doc.sha256 or "",
                check_status=check.status,
                check_source=check.source,
                reason=check.reason,
                officer_name=user.full_name if user else "",
                officer_username=user.username if user else "",
            )

        if out.source_document_id is not None:
            db.add(
                Evidence(
                    evaluation_id=row.id,
                    document_id=out.source_document_id,
                    page=out.source_page,
                    snippet=out.evidence,
                    field_name=out.rule_trace.get("field", ""),
                    field_value=str(out.rule_trace.get("observed", "")),
                    match_score=out.confidence,
                    rank=1,
                )
            )

    _apply_summary_to_bid(bid, rows)
    bid.status = "EVALUATED"
    bid.evaluated_at = datetime.now(timezone.utc)
    db.commit()


def _load_results(bid_id: int, db: Session) -> EvaluationResultsOut:
    bid = get_bid_or_404(bid_id, db)

    rows = (
        db.query(Evaluation)
        .filter(Evaluation.bid_id == bid_id)
        .order_by(Evaluation.id)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                "No evaluation has been run for this bid yet. "
                "Run a compliance evaluation first."
            ),
        )

    results: list[ResultOut] = []
    for row in rows:
        req = row.requirement
        ev = row.evidence[0] if row.evidence else None
        results.append(
            ResultOut(
                requirement_id=req.id,
                requirement_code=req.code,
                requirement_title=req.title,
                category=req.category,
                obligation=req.obligation,
                expected_condition=(req.rule_params or {}).get("expected_display", ""),
                verdict=_effective_verdict(row),
                score=_effective_score(row),
                confidence=row.confidence,
                evidence=ev.snippet if ev else "",
                source_document=ev.document.original_filename if ev else "",
                source_document_id=ev.document_id if ev else None,
                source_page=ev.page if ev else 0,
                explanation=row.explanation,
                recommended_action=row.recommended_action,
                decision_source=row.decision_source,
                rule_trace=row.rule_trace or {},
                extraction_method=(row.rule_trace or {}).get("extraction_method", ""),
                citation_status=(row.rule_trace or {}).get("citation_status", ""),
                system_verdict=row.verdict,
                overridden=row.officer_verdict is not None,
                officer_verdict=row.officer_verdict,
                override_reason=row.override_reason or "",
                override_category=row.override_category or "",
                officer_name=row.officer_name or "",
                officer_username=row.officer_username or "",
                verification_required=bool(req.verification_required),
                verification_status=row.verification_status or "NOT_APPLICABLE",
                verification_reason=row.verification_reason or "",
                verification_source=row.verification_source or "",
                verification_checked_at=row.verification_checked_at or "",
                verification_details=row.verification_details or {},
                rule_verdict=(row.rule_trace or {}).get("rule_verdict", row.verdict),
                overridden_at=row.overridden_at,
            )
        )

    # Recompute from stored rows so the summary always matches the results.
    summary = compute_summary(
        [
            SimpleNamespace(verdict=r.verdict, score=r.score, obligation=r.obligation)
            for r in results
        ]
    )

    return EvaluationResultsOut(
        bid=BidOut.model_validate(bid),
        tender=TenderOut.model_validate(bid.tender),
        summary=SummaryOut(**summary),
        results=results,
    )


@router.post("", response_model=EvaluationResultsOut, status_code=201)
def create_evaluation(
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    _run_evaluation(payload.bid_id, db, user)
    return _load_results(payload.bid_id, db)


@router.get("/{bid_id}", response_model=EvaluationResultsOut)
def get_evaluation(bid_id: int, db: Session = Depends(get_db)):
    return _load_results(bid_id, db)


@router.get("/{bid_id}/results", response_model=EvaluationResultsOut)
def get_evaluation_results(bid_id: int, db: Session = Depends(get_db)):
    return _load_results(bid_id, db)


@router.post("/{bid_id}/overrides", response_model=EvaluationResultsOut, status_code=201)
def create_override(
    bid_id: int,
    payload: OverrideCreate,
    db: Session = Depends(get_db),
    officer: User = Depends(require_officer),
):
    """Record an officer's verdict for one requirement and audit it.

    The officer is the logged-in user: the name and username on the
    evaluation row and the audit event come from the session only.
    """
    bid = get_bid_or_404(bid_id, db)

    verdict = payload.verdict.strip().upper()
    category = payload.reason_category.strip().upper()
    reason = payload.reason.strip()
    officer_name = officer.full_name

    if verdict not in VERDICTS:
        raise HTTPException(
            status_code=422,
            detail=f"Verdict must be one of {', '.join(VERDICTS)}.",
        )
    if category not in REASON_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                "A reason category is required. Choose one of: "
                + "; ".join(REASON_CATEGORIES.values())
                + "."
            ),
        )
    if len(reason) < MIN_REASON_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Details and reference of at least {MIN_REASON_LENGTH} "
                "characters are required."
            ),
        )

    row = (
        db.query(Evaluation)
        .filter(
            Evaluation.bid_id == bid_id,
            Evaluation.requirement_id == payload.requirement_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No evaluation result for requirement {payload.requirement_id} "
                "on this bid. Run a compliance evaluation first."
            ),
        )
    if verdict == _effective_verdict(row):
        raise HTTPException(
            status_code=409,
            detail=f"The requirement's verdict is already {verdict}.",
        )

    at = datetime.now(timezone.utc)
    if verdict == row.verdict:
        # Setting it back to the system's verdict withdraws the override.
        row.officer_verdict = None
        row.override_reason = ""
        row.override_category = ""
        row.officer_name = ""
        row.officer_username = ""
        row.overridden_at = None
    else:
        row.officer_verdict = verdict
        row.override_reason = reason
        row.override_category = category
        row.officer_name = officer_name
        row.officer_username = officer.username
        row.overridden_at = at

    append_event(
        db,
        "VERDICT_OVERRIDE",
        timestamp=utc_timestamp(at),
        bid_id=bid.id,
        bidder_name=bid.bidder_name,
        requirement_id=row.requirement.id,
        requirement_code=row.requirement.code,
        requirement_title=row.requirement.title,
        system_verdict=row.verdict,
        officer_verdict=verdict,
        reason=reason,
        reason_category=category,
        officer_name=officer_name,
        officer_username=officer.username,
    )

    rows = db.query(Evaluation).filter(Evaluation.bid_id == bid_id).all()
    _apply_summary_to_bid(bid, rows)
    db.commit()
    return _load_results(bid_id, db)
