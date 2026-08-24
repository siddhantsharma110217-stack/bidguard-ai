"""Evaluation endpoints.

A bid has exactly one current evaluation, so the bid id doubles as the
evaluation id — `POST /api/evaluations` runs (or re-runs) the evaluation for
a bid and returns results keyed by that id.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.bids import get_bid_or_404
from app.db import get_db
from app.evaluation.evaluator import get_evaluator
from app.evaluation.scoring import compute_summary
from app.models import Document, Evaluation, Evidence, Requirement
from app.schemas import (
    BidOut,
    EvaluationCreate,
    EvaluationResultsOut,
    ResultOut,
    SummaryOut,
    TenderOut,
)

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _run_evaluation(bid_id: int, db: Session) -> None:
    """Evaluate every requirement for the bid and persist the results."""
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

    # Clear any previous run so re-evaluating is idempotent.
    prior = db.query(Evaluation).filter(Evaluation.bid_id == bid_id).all()
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

    for out in outcomes:
        row = Evaluation(
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
        db.add(row)
        db.flush()

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

    summary = compute_summary(outcomes)
    bid.compliance_score = summary["overall_compliance"]
    bid.risk_score = summary["risk_score"]
    bid.risk_band = summary["risk_band"]
    bid.gate_status = summary["gate_status"]
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
                verdict=row.verdict,
                score=row.score,
                confidence=row.confidence,
                evidence=ev.snippet if ev else "",
                source_document=ev.document.original_filename if ev else "",
                source_document_id=ev.document_id if ev else None,
                source_page=ev.page if ev else 0,
                explanation=row.explanation,
                recommended_action=row.recommended_action,
                decision_source=row.decision_source,
                rule_trace=row.rule_trace or {},
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
def create_evaluation(payload: EvaluationCreate, db: Session = Depends(get_db)):
    _run_evaluation(payload.bid_id, db)
    return _load_results(payload.bid_id, db)


@router.get("/{bid_id}", response_model=EvaluationResultsOut)
def get_evaluation(bid_id: int, db: Session = Depends(get_db)):
    return _load_results(bid_id, db)


@router.get("/{bid_id}/results", response_model=EvaluationResultsOut)
def get_evaluation_results(bid_id: int, db: Session = Depends(get_db)):
    return _load_results(bid_id, db)
