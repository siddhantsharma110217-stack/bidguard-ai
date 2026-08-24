"""Unit tests for the deterministic mock compliance evaluator.

These exercise the evaluator directly against synthetic requirements and
documents, proving each verdict path is driven by the rule + evidence and
not by hard-coded per-requirement answers.
"""

from types import SimpleNamespace

import pytest

from app.evaluation.mock_evaluator import MockComplianceEvaluator
from app.evaluation.scoring import compute_summary, score_for_verdict


def make_req(**kw):
    base = dict(
        id=1,
        code="REQ-001",
        category="TECHNICAL",
        title="Test Requirement",
        description="",
        obligation="MANDATORY",
        rule_type="numeric_min",
        rule_params={"field": "ram_gb", "threshold": 16, "unit": "GB",
                     "expected_display": "Minimum 16 GB"},
        weight=3,
        source_page=1,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def make_doc(fields, doc_id=1, name="Technical_Bid.pdf"):
    return SimpleNamespace(id=doc_id, original_filename=name, fields=fields)


@pytest.fixture()
def evaluator():
    return MockComplianceEvaluator()


# ---------- verdict paths ----------

def test_numeric_min_pass(evaluator):
    req = make_req()
    doc = make_doc({"ram_gb": {"value": "16 GB", "numeric": 16, "confidence": 0.98}})
    [out] = evaluator.evaluate_bid([req], [doc])

    assert out.verdict == "PASS"
    assert out.score == 100.0
    assert out.decision_source == "RULE"
    assert out.source_document == "Technical_Bid.pdf"
    assert out.rule_trace["passed"] is True
    assert out.rule_trace["observed"] == 16


def test_numeric_min_fail_explains_shortfall(evaluator):
    req = make_req()
    doc = make_doc({"ram_gb": {"value": "8 GB", "numeric": 8, "confidence": 0.98}})
    [out] = evaluator.evaluate_bid([req], [doc])

    assert out.verdict == "FAIL"
    assert out.score == 0.0
    assert out.rule_trace["passed"] is False
    assert "8" in out.explanation and "16" in out.explanation
    assert "below the required minimum" in out.explanation


def test_numeric_max_fail(evaluator):
    req = make_req(
        rule_type="numeric_max",
        rule_params={"field": "delivery_days", "threshold": 30, "unit": "days",
                     "expected_display": "Within 30 days"},
    )
    doc = make_doc({"delivery_days": {"value": "45 days", "numeric": 45, "confidence": 0.95}})
    [out] = evaluator.evaluate_bid([req], [doc])

    assert out.verdict == "FAIL"
    assert "exceeding the permitted maximum" in out.explanation


def test_missing_when_no_document_supplies_field(evaluator):
    req = make_req(
        rule_type="presence",
        rule_params={"field": "oem_authorization_ref",
                     "expected_display": "OEM authorisation"},
    )
    doc = make_doc({"ram_gb": {"value": "16 GB", "numeric": 16, "confidence": 0.9}})
    [out] = evaluator.evaluate_bid([req], [doc])

    assert out.verdict == "MISSING"
    assert out.score == 0.0
    assert out.source_document == ""
    assert out.source_document_id is None
    assert "No supporting evidence" in out.explanation
    assert out.rule_trace["reason"] == "field_not_present_in_any_document"


def test_review_when_evidence_is_ambiguous(evaluator):
    req = make_req(
        rule_type="presence",
        rule_params={"field": "bis_registration_no", "expected_display": "BIS certificate"},
    )
    doc = make_doc({
        "bis_registration_no": {
            "value": "R-4119____",
            "confidence": 0.42,
            "ambiguous": True,
            "ambiguity_reason": "the scan is partially illegible",
        }
    })
    [out] = evaluator.evaluate_bid([req], [doc])

    assert out.verdict == "REVIEW"
    assert out.score == 60.0
    assert out.decision_source == "HUMAN_REVIEW"
    assert "partially illegible" in out.explanation
    assert out.rule_trace["reason"] == "ambiguous_evidence"


def test_review_when_confidence_below_threshold(evaluator):
    """A rule that would PASS is downgraded to REVIEW on low confidence."""
    req = make_req()
    doc = make_doc({"ram_gb": {"value": "16 GB", "numeric": 16, "confidence": 0.55}})
    [out] = evaluator.evaluate_bid([req], [doc])

    assert out.verdict == "REVIEW"
    assert out.decision_source == "HUMAN_REVIEW"


def test_tier_min_processor(evaluator):
    req = make_req(
        rule_type="tier_min",
        rule_params={"field": "processor", "minimum": "i5",
                     "expected_display": "Intel Core i5 or higher"},
    )
    ok = make_doc({"processor": {"value": "Intel Core i7-1355U", "confidence": 0.96}})
    bad = make_doc({"processor": {"value": "Intel Core i3-1215U", "confidence": 0.96}})

    assert evaluator.evaluate_bid([req], [ok])[0].verdict == "PASS"
    assert evaluator.evaluate_bid([req], [bad])[0].verdict == "FAIL"


def test_text_contains_any(evaluator):
    req = make_req(
        rule_type="text_contains_any",
        rule_params={"field": "operating_system",
                     "options": ["Windows 11 Pro", "Windows 11 Professional"],
                     "expected_display": "Windows 11 Professional"},
    )
    ok = make_doc({"operating_system": {"value": "Windows 11 Pro 64-bit", "confidence": 0.99}})
    bad = make_doc({"operating_system": {"value": "Windows 11 Home", "confidence": 0.99}})

    assert evaluator.evaluate_bid([req], [ok])[0].verdict == "PASS"
    assert evaluator.evaluate_bid([req], [bad])[0].verdict == "FAIL"


def test_field_lookup_is_document_order_independent(evaluator):
    """Documents are searched by id, so package ordering cannot change results."""
    req = make_req()
    d1 = make_doc({"ram_gb": {"value": "16 GB", "numeric": 16, "confidence": 0.98}},
                  doc_id=1, name="First.pdf")
    d2 = make_doc({"ram_gb": {"value": "8 GB", "numeric": 8, "confidence": 0.98}},
                  doc_id=2, name="Second.pdf")

    a = evaluator.evaluate_bid([req], [d1, d2])[0]
    b = evaluator.evaluate_bid([req], [d2, d1])[0]

    assert a.verdict == b.verdict == "PASS"
    assert a.source_document == b.source_document == "First.pdf"


# ---------- scoring ----------

def test_verdict_scores():
    assert score_for_verdict("PASS") == 100.0
    assert score_for_verdict("REVIEW") == 60.0
    assert score_for_verdict("FAIL") == 0.0
    assert score_for_verdict("MISSING") == 0.0


def test_compute_summary_matches_target_mix():
    """7 PASS + 1 REVIEW + 1 FAIL + 1 MISSING -> 76.0%."""
    outcomes = (
        [SimpleNamespace(verdict="PASS", score=100.0, obligation="MANDATORY")] * 7
        + [SimpleNamespace(verdict="REVIEW", score=60.0, obligation="MANDATORY")]
        + [SimpleNamespace(verdict="FAIL", score=0.0, obligation="MANDATORY")]
        + [SimpleNamespace(verdict="MISSING", score=0.0, obligation="MANDATORY")]
    )
    s = compute_summary(outcomes)

    assert s["total_requirements"] == 10
    assert (s["passed"], s["review"], s["failed"], s["missing"]) == (7, 1, 1, 1)
    assert s["overall_compliance"] == 76.0
    assert s["risk_band"] == "HIGH"
    assert s["gate_status"] == "NON_RESPONSIVE"


def test_summary_empty_is_safe():
    s = compute_summary([])
    assert s["total_requirements"] == 0
    assert s["overall_compliance"] == 0.0
    assert s["gate_status"] == "RESPONSIVE"


def test_desirable_failure_does_not_block_responsiveness():
    outcomes = [
        SimpleNamespace(verdict="PASS", score=100.0, obligation="MANDATORY"),
        SimpleNamespace(verdict="FAIL", score=0.0, obligation="DESIRABLE"),
    ]
    assert compute_summary(outcomes)["gate_status"] == "RESPONSIVE"
