"""ComplianceEvaluator abstraction.

The pipeline depends only on this Protocol, never on a concrete evaluator.
`MockComplianceEvaluator` is the deterministic offline implementation used
for the demo; an LLM-backed evaluator can be dropped in later by
implementing the same `evaluate_bid` signature and returning the same
`EvaluationOutcome` shape.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class EvaluationOutcome:
    """One requirement judged against one bidder's document package."""

    requirement_id: int
    requirement_code: str
    requirement_title: str
    category: str
    obligation: str  # MANDATORY | DESIRABLE
    expected_condition: str

    verdict: str  # PASS | REVIEW | FAIL | MISSING
    score: float
    confidence: float

    evidence: str  # the extracted value / quoted snippet
    source_document: str  # filename, or "" when nothing was found
    source_document_id: int | None
    source_page: int

    explanation: str
    recommended_action: str
    decision_source: str  # RULE | AI | RULE+AI | HUMAN_REVIEW
    rule_trace: dict = field(default_factory=dict)


class ComplianceEvaluator(Protocol):
    def evaluate_bid(self, requirements: list, documents: list) -> list[EvaluationOutcome]:
        """Judge every requirement against the bidder's documents.

        Args:
            requirements: Requirement ORM rows for the tender.
            documents: Document ORM rows belonging to the bid.

        Returns:
            One EvaluationOutcome per requirement, in requirement order.
        """
        ...


def get_evaluator() -> ComplianceEvaluator:
    """Select the active evaluator implementation."""
    from app.evaluation.mock_evaluator import MockComplianceEvaluator

    return MockComplianceEvaluator()
