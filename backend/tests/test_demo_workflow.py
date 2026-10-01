"""End-to-end test of the demo workflow through the HTTP API.

Mirrors exactly what the browser demo does:
  Load Demo -> Requirements -> Documents -> Run Evaluation -> Results -> Dashboard
"""

import pytest

from app.main import app
from tests.auth_helpers import officer_client


@pytest.fixture(scope="module")
def client():
    with officer_client() as c:
        yield c


@pytest.fixture(scope="module")
def demo(client):
    """Load a clean demo dataset once for this module."""
    resp = client.post("/api/demo/load", params={"reset": True})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------- 1. tender loading ----------

def test_demo_load_creates_tender_and_bid(demo):
    assert demo["tender"]["title"] == "Supply of Laptop Computers for Government Office"
    assert demo["tender"]["reference_no"] == "GEM/2026/B/4471902"
    assert demo["bid"]["bidder_name"] == "TechNova Systems Pvt. Ltd."
    assert demo["requirement_count"] == 10
    assert demo["document_count"] == 4


def test_demo_load_is_idempotent(client, demo):
    """Clicking Load Demo again must not duplicate tenders."""
    again = client.post("/api/demo/load")
    assert again.status_code == 200
    assert again.json()["tender"]["id"] == demo["tender"]["id"]

    tenders = client.get("/api/tenders").json()
    matching = [t for t in tenders if t["reference_no"] == "GEM/2026/B/4471902"]
    assert len(matching) == 1


def test_get_tender(client, demo):
    resp = client.get(f"/api/tenders/{demo['tender']['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"


def test_missing_tender_returns_clean_404(client):
    resp = client.get("/api/tenders/999999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
    assert "Traceback" not in resp.text


# ---------- 2. requirement extraction ----------

def test_requirements_listing(client, demo):
    resp = client.get(f"/api/tenders/{demo['tender']['id']}/requirements")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 10
    assert body["mandatory"] == 9
    assert body["desirable"] == 1

    codes = [r["code"] for r in body["requirements"]]
    assert codes == [f"REQ-{i:03d}" for i in range(1, 11)]

    # Every requirement must carry the fields the UI table renders.
    for r in body["requirements"]:
        assert r["category"] in {"TECHNICAL", "COMPLIANCE", "DELIVERY", "LEGAL", "FINANCIAL"}
        assert r["obligation"] in {"MANDATORY", "DESIRABLE"}
        assert r["expected_condition"]
        assert r["source_clause"]


# ---------- 3. bidder documents ----------

def test_bid_documents(client, demo):
    resp = client.get(f"/api/bids/{demo['bid']['id']}/documents")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total"] == 4
    names = {d["original_filename"] for d in body["documents"]}
    assert names == {
        "Technical_Bid.pdf",
        "Warranty_Certificate.pdf",
        "Commercial_Bid.pdf",
        "BIS_Certificate_Scan.pdf",
    }

    scan = next(d for d in body["documents"] if d["original_filename"] == "BIS_Certificate_Scan.pdf")
    assert scan["has_text_layer"] is False
    assert scan["doc_type"] == "BIS_CERTIFICATE"


def test_missing_bid_returns_clean_404(client):
    resp = client.get("/api/bids/999999/documents")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------- 4. compliance evaluation ----------

@pytest.fixture(scope="module")
def results(client, demo):
    resp = client.post("/api/evaluations", json={"bid_id": demo["bid"]["id"]})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_evaluation_returns_all_requirements(results):
    assert len(results["results"]) == 10


def test_target_verdict_mix(results):
    s = results["summary"]
    assert s["total_requirements"] == 10
    assert s["passed"] == 7
    assert s["review"] == 1
    assert s["failed"] == 1
    assert s["missing"] == 1


def test_overall_compliance_is_76_percent(results):
    assert results["summary"]["overall_compliance"] == 76.0


def test_risk_is_high_and_bid_is_non_responsive(results):
    s = results["summary"]
    assert s["risk_band"] == "HIGH"
    assert s["gate_status"] == "NON_RESPONSIVE"
    assert s["blocking_requirements"] == 2
    assert results["bid"]["status"] == "EVALUATED"
    assert results["bid"]["compliance_score"] == 76.0


def test_specific_verdicts_per_requirement(results):
    by_code = {r["requirement_code"]: r for r in results["results"]}

    expected = {
        "REQ-001": "PASS",     # Intel Core i5-13420H
        "REQ-002": "PASS",     # 16 GB
        "REQ-003": "PASS",     # 512 GB SSD
        "REQ-004": "PASS",     # 15.6 inch
        "REQ-005": "PASS",     # Windows 11 Pro
        "REQ-006": "PASS",     # 3 years onsite
        "REQ-007": "REVIEW",   # BIS scan illegible
        "REQ-008": "FAIL",     # 45 days vs 30
        "REQ-009": "MISSING",  # no OEM authorisation
        "REQ-010": "PASS",     # ENERGY STAR
    }
    for code, verdict in expected.items():
        assert by_code[code]["verdict"] == verdict, f"{code} expected {verdict}"


def test_fail_result_explains_why(results):
    fail = next(r for r in results["results"] if r["verdict"] == "FAIL")
    assert fail["requirement_code"] == "REQ-008"
    assert fail["score"] == 0.0
    assert "45" in fail["explanation"] and "30" in fail["explanation"]
    assert fail["source_document"] == "Commercial_Bid.pdf"
    assert fail["decision_source"] == "RULE"
    assert fail["rule_trace"]["observed"] == 45
    assert fail["rule_trace"]["required_maximum"] == 30
    assert fail["recommended_action"]


def test_missing_result_has_no_invented_evidence(results):
    missing = next(r for r in results["results"] if r["verdict"] == "MISSING")
    assert missing["requirement_code"] == "REQ-009"
    assert missing["evidence"] == ""
    assert missing["source_document"] == ""
    assert missing["source_document_id"] is None
    assert "No supporting evidence" in missing["explanation"]


def test_review_result_recommends_human_verification(results):
    review = next(r for r in results["results"] if r["verdict"] == "REVIEW")
    assert review["requirement_code"] == "REQ-007"
    assert review["score"] == 60.0
    assert review["decision_source"] == "HUMAN_REVIEW"
    assert review["source_document"] == "BIS_Certificate_Scan.pdf"
    assert "verification" in review["recommended_action"].lower()


def test_pass_results_carry_evidence_and_source(results):
    passes = [r for r in results["results"] if r["verdict"] == "PASS"]
    assert len(passes) == 7
    for r in passes:
        assert r["score"] == 100.0
        assert r["evidence"], f"{r['requirement_code']} has no evidence snippet"
        assert r["source_document"]
        assert r["confidence"] >= 0.70


def test_scores_sum_to_overall(results):
    total = sum(r["score"] for r in results["results"])
    expected = round(total / len(results["results"]), 1)
    assert results["summary"]["overall_compliance"] == expected


# ---------- 5. determinism ----------

def test_evaluation_is_deterministic(client, demo):
    """Re-running must produce byte-identical results, not duplicates."""
    first = client.post("/api/evaluations", json={"bid_id": demo["bid"]["id"]}).json()
    second = client.post("/api/evaluations", json={"bid_id": demo["bid"]["id"]}).json()

    assert first["summary"] == second["summary"]
    assert [(r["requirement_code"], r["verdict"], r["score"], r["explanation"])
            for r in first["results"]] == \
           [(r["requirement_code"], r["verdict"], r["score"], r["explanation"])
            for r in second["results"]]
    assert len(second["results"]) == 10  # no accumulation of stale rows


# ---------- 6. reading results back ----------

def test_get_results_endpoint(client, demo, results):
    resp = client.get(f"/api/evaluations/{demo['bid']['id']}/results")
    assert resp.status_code == 200
    assert resp.json()["summary"] == results["summary"]


def test_results_for_unevaluated_bid_return_clean_404(client, demo):
    new_bid = client.post(
        "/api/bids",
        json={"tender_id": demo["tender"]["id"], "bidder_name": "Unevaluated Ltd."},
    ).json()

    resp = client.get(f"/api/evaluations/{new_bid['id']}/results")
    assert resp.status_code == 404
    assert "no evaluation has been run" in resp.json()["detail"].lower()


def test_evaluating_bid_without_documents_is_rejected(client, demo):
    empty_bid = client.post(
        "/api/bids",
        json={"tender_id": demo["tender"]["id"], "bidder_name": "No Documents Ltd."},
    ).json()

    resp = client.post("/api/evaluations", json={"bid_id": empty_bid["id"]})
    assert resp.status_code == 409
    assert "no submitted documents" in resp.json()["detail"].lower()
    assert "Traceback" not in resp.text


def test_evaluating_unknown_bid_returns_404(client):
    resp = client.post("/api/evaluations", json={"bid_id": 999999})
    assert resp.status_code == 404


# ---------- 7. dashboard ----------

def test_dashboard_reflects_real_data(client, demo, results):
    body = client.get("/api/dashboard").json()

    assert body["demo_loaded"] is True
    assert body["demo_tender_id"] == demo["tender"]["id"]
    assert body["demo_bid_id"] == demo["bid"]["id"]
    assert body["active_tenders"] >= 1
    assert body["bids_evaluated"] >= 1
    assert body["avg_compliance"] == 76.0
    assert body["high_risk_bids"] >= 1


# ---------- 8. health ----------

def test_health_still_ok(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ai_provider"] == "mock"


def test_evaluated_at_is_timezone_aware(results):
    """The UI parses this with `new Date()`; a naive string would be read as
    local time and display the wrong moment."""
    ts = results["bid"]["evaluated_at"]
    assert ts is not None
    assert ts.endswith("+00:00") or ts.endswith("Z"), ts

    from datetime import datetime

    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
