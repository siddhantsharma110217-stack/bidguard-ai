"""Document trust layer: issuer verification, its interaction with
compliance verdicts, file re-verification, signatures, flags and audit."""

import re
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
from sqlalchemy import text

from app.audit import HASHED_FIELDS, _sha256_json, append_event
from app.config import settings
from app.db import engine
from app.evaluation.evaluator import EvaluationOutcome
from app.verification.adapter import (
    NOT_APPLICABLE,
    UNVERIFIED,
    VERIFICATION_FAILED,
    VERIFIED,
    BisCertificateAdapter,
    Submitted,
    VerificationResult,
)
from app.verification.registry import SOURCE_NAME, normalise_company
from app.verification.service import apply_verification, verify_outcome
from tests.auth_helpers import OFFICER_NAME, OFFICER_USERNAME, officer_client, reviewer_client
from tests.pdf_helpers import COMPLIANT_PAGES, demo_requirements, make_pdf

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "samples"
TECHNOVA = "TechNova Systems Pvt. Ltd."
APEX = "Apex Infotech Solutions"
BHARAT = "Bharat Digital Technologies Pvt. Ltd."
CRESTLINE = "Crestline Computers LLP"
REASON = "Original certificate checked with the issuer by phone on 12-03-2026."


# ---------- adapter: each status ----------

ADAPTER = BisCertificateAdapter()


def check(number, holder):
    return ADAPTER.verify(Submitted(number, holder, "test", document_name="BIS.pdf", page=1))


def test_verified_when_number_and_holder_match():
    r = check("R-41190527", "TechNova Systems Pvt. Ltd.")
    assert r.status == VERIFIED
    assert r.source == SOURCE_NAME == "Demo Certification Authority (fictional)"
    assert r.checked_at.endswith("+00:00")
    assert [m.field for m in r.matched] == ["certificate_number", "holder"]
    assert r.mismatched == []
    assert r.issuer_record["valid_until"] == "31/12/2027"


def test_matched_company_with_mismatched_number_fails():
    r = check("R-41087632", "Apex Infotech Solutions")
    assert r.status == VERIFICATION_FAILED
    assert [(m.field, m.submitted, m.issuer) for m in r.mismatched] == [
        ("certificate_number", "R-41087632", "R-41087623")
    ]
    assert [(m.field, m.submitted, m.issuer) for m in r.matched] == [
        ("holder", "Apex Infotech Solutions", "Apex Infotech Solutions")
    ]
    assert r.reason == "The certificate number does not match the issuer record for this company."


def test_mismatched_company_fails():
    r = check("R-41099887", "Arcadia Computing Ltd.")
    assert r.status == VERIFICATION_FAILED
    assert [(m.field, m.submitted, m.issuer) for m in r.mismatched] == [
        ("holder", "Arcadia Computing Ltd.", "Summit Ridge Computers Pvt. Ltd.")
    ]
    assert [m.field for m in r.matched] == ["certificate_number"]
    assert "different company" in r.reason


@pytest.mark.parametrize("number", ["R-41052219", "R-99999999"])
def test_unverified_when_no_issuer_record(number):
    r = check(number, "Nobody Registered Ltd")
    assert r.status == UNVERIFIED
    assert r.issuer_record is None and r.matched == [] and r.mismatched == []
    assert "No issuer record" in r.reason


@pytest.mark.parametrize("number", ["", "   ", "____"])
def test_unverified_when_no_number_readable(number):
    r = check(number, "TechNova Systems Pvt. Ltd.")
    assert r.status == UNVERIFIED
    assert "No certificate number could be read" in r.reason


def test_number_and_company_normalisation():
    assert check(" r 41190527 ", "TECHNOVA SYSTEMS PRIVATE LIMITED").status == VERIFIED
    assert normalise_company("Crestline Computers LLP") == normalise_company("crestline computers")


def test_adapter_handles_only_its_requirement():
    reqs = {r.code: r for r in demo_requirements()}
    assert ADAPTER.can_verify(reqs["REQ-007"])
    assert not any(ADAPTER.can_verify(r) for c, r in reqs.items() if c != "REQ-007")


# ---------- not applicable ----------

def _outcome(verdict, doc_id=1):
    return EvaluationOutcome(
        requirement_id=7, requirement_code="REQ-007", requirement_title="BIS Certification",
        category="COMPLIANCE", obligation="MANDATORY", expected_condition="",
        verdict=verdict, score=0.0, confidence=0.9, evidence="", source_document="BIS.pdf",
        source_document_id=doc_id, source_page=1, explanation="Rule explanation.",
        recommended_action="No action required.", decision_source="RULE", rule_trace={},
    )


def _req(required=True):
    r = {x.code: x for x in demo_requirements()}["REQ-007"]
    r.verification_required = required
    return r


DOC = SimpleNamespace(id=1, original_filename="BIS.pdf", fields={
    "bis_registration_no": {"value": "R-41190527", "page": 1},
    "certificate_holder": {"value": "TechNova Systems Pvt. Ltd.", "page": 1},
})


def test_not_applicable_when_not_required_or_missing():
    assert verify_outcome(_req(False), _outcome("PASS"), [DOC], TECHNOVA).status == NOT_APPLICABLE
    missing = verify_outcome(_req(), _outcome("MISSING", doc_id=None), [DOC], TECHNOVA)
    assert missing.status == NOT_APPLICABLE and "nothing to verify" in missing.reason


def test_holder_falls_back_to_bidder_name():
    doc = SimpleNamespace(id=1, original_filename="BIS.pdf", fields={"bis_registration_no": {"value": "R-41093340", "page": 1}})
    r = verify_outcome(_req(), _outcome("PASS"), [doc], CRESTLINE)
    assert r.status == VERIFIED
    assert r.submitted["holder_source"].startswith("Bidder company name")


def test_unconfirmed_ai_citation_is_unverified():
    doc = SimpleNamespace(id=1, original_filename="BIS.pdf", fields={
        "bis_registration_no": {"value": "R-41190527", "page": 1, "citation_status": "UNSUPPORTED"},
    })
    assert verify_outcome(_req(), _outcome("REVIEW"), [doc], TECHNOVA).status == UNVERIFIED


# ---------- rule interaction ----------

def _result(status, clause="the certificate number does not match the issuer record"):
    return VerificationResult(status=status, reason="r", clause=clause, source=SOURCE_NAME)


@pytest.mark.parametrize("status", [UNVERIFIED, VERIFICATION_FAILED])
def test_pass_becomes_review(status):
    out = _outcome("PASS")
    out.score = 100.0
    apply_verification(out, _result(status))
    assert (out.verdict, out.score) == ("REVIEW", 60.0)
    assert out.decision_source == "RULE+VERIFICATION"
    assert out.rule_trace["rule_verdict"] == "PASS"
    assert out.explanation.startswith(
        "Evidence meets the requirement, but the certificate number does not match the "
        "issuer record. Officer review required."
    )


@pytest.mark.parametrize("verdict", ["FAIL", "MISSING", "REVIEW"])
@pytest.mark.parametrize("status", [VERIFIED, UNVERIFIED, VERIFICATION_FAILED, NOT_APPLICABLE])
def test_other_verdicts_never_change(verdict, status):
    out = _outcome(verdict)
    apply_verification(out, _result(status))
    assert out.verdict == verdict and out.explanation == "Rule explanation."


@pytest.mark.parametrize("status", [VERIFIED, NOT_APPLICABLE])
def test_verified_or_not_applicable_keeps_pass(status):
    out = _outcome("PASS")
    apply_verification(out, _result(status))
    assert out.verdict == "PASS"


def test_verification_never_produces_fail():
    for verdict in ("PASS", "REVIEW", "FAIL", "MISSING"):
        for status in (VERIFIED, UNVERIFIED, VERIFICATION_FAILED, NOT_APPLICABLE):
            out = _outcome(verdict)
            apply_verification(out, _result(status))
            assert out.verdict != "FAIL" or verdict == "FAIL"


# ---------- demo bidders through the API ----------

@pytest.fixture(scope="module")
def client():
    with officer_client() as c:
        yield c


@pytest.fixture()
def demo(client):
    loaded = client.post("/api/demo/load", params={"reset": True}).json()
    results = {}
    for bid in loaded["bids"]:
        resp = client.post("/api/evaluations", json={"bid_id": bid["id"]})
        assert resp.status_code == 201, resp.text
        results[bid["bidder_name"]] = resp.json()
    return {"tender": loaded["tender"]["id"], "bids": {b["bidder_name"]: b["id"] for b in loaded["bids"]}, "results": results}


def _req_result(results, code="REQ-007"):
    return next(r for r in results["results"] if r["requirement_code"] == code)


@pytest.mark.parametrize(
    "bidder, status, verdict, rule_verdict",
    [
        (TECHNOVA, VERIFIED, "REVIEW", "REVIEW"),  # REVIEW (unreadable validity) is kept
        (BHARAT, UNVERIFIED, "REVIEW", "PASS"),
        (APEX, VERIFICATION_FAILED, "REVIEW", "PASS"),
        (CRESTLINE, VERIFIED, "PASS", "PASS"),
    ],
)
def test_demo_bidder_verification(demo, bidder, status, verdict, rule_verdict):
    r = _req_result(demo["results"][bidder])
    assert r["verification_required"] is True
    assert (r["verification_status"], r["verdict"], r["rule_verdict"]) == (status, verdict, rule_verdict)
    assert r["verification_source"] == SOURCE_NAME
    assert r["verification_reason"]
    assert re.match(r"\d{4}-\d{2}-\d{2}T.*\+00:00$", r["verification_checked_at"])


def test_apex_details_show_submitted_and_issuer_values(demo):
    r = _req_result(demo["results"][APEX])
    details = r["verification_details"]
    assert details["mismatched"] == [{
        "field": "certificate_number", "label": "Certificate number",
        "submitted": "R-41087632", "issuer": "R-41087623",
    }]
    assert details["matched"][0]["field"] == "holder"
    assert details["submitted"]["document_name"] == "BIS_Certificate.pdf"
    assert r["explanation"].startswith(
        "Evidence meets the requirement, but the certificate number does not match the issuer "
        "record. Officer review required."
    )
    assert "Verification failed — officer review required" in r["recommended_action"]


def test_bharat_unverified_has_no_issuer_record(demo):
    r = _req_result(demo["results"][BHARAT])
    assert r["verification_details"]["issuer_record"] is None
    assert "no issuer record" in r["explanation"].lower()


def test_technova_baseline_unchanged(demo):
    s = demo["results"][TECHNOVA]["summary"]
    assert (s["passed"], s["review"], s["failed"], s["missing"]) == (7, 1, 1, 1)
    assert (s["overall_compliance"], s["risk_score"], s["gate_status"]) == (76.0, 53.0, "NON_RESPONSIVE")


def test_non_flagged_requirements_are_unchanged(demo):
    for bidder, results in demo["results"].items():
        for r in results["results"]:
            if r["requirement_code"] == "REQ-007":
                continue
            assert r["verification_required"] is False
            assert r["verification_status"] == NOT_APPLICABLE
            assert r["rule_verdict"] == r["verdict"]
            assert r["decision_source"] != "RULE+VERIFICATION"
            assert "issuer" not in r["explanation"].lower()


def test_override_on_verified_requirement_keeps_status_visible(client, demo):
    bid = demo["bids"][APEX]
    req = _req_result(demo["results"][APEX])["requirement_id"]
    resp = client.post(f"/api/evaluations/{bid}/overrides", json={
        "requirement_id": req, "verdict": "PASS", "reason_category": "COMMITTEE_DECISION", "reason": REASON,
    })
    assert resp.status_code == 201, resp.text
    r = _req_result(resp.json())
    assert (r["verdict"], r["system_verdict"], r["overridden"]) == ("PASS", "REVIEW", True)
    assert r["verification_status"] == VERIFICATION_FAILED
    # Still visible, and the override still holds, after a re-run.
    rerun = _req_result(client.post("/api/evaluations", json={"bid_id": bid}).json())
    assert (rerun["verdict"], rerun["verification_status"]) == ("PASS", VERIFICATION_FAILED)


def test_documents_show_verification_per_document(client, demo):
    docs = client.get(f"/api/bids/{demo['bids'][APEX]}/documents").json()["documents"]
    by_name = {d["original_filename"]: d for d in docs}
    assert by_name["BIS_Certificate.pdf"]["verification_status"] == VERIFICATION_FAILED
    assert by_name["Technical_Bid.pdf"]["verification_status"] == ""
    assert all(d["has_signature_field"] is None and not d["reverifiable"] for d in docs)


# ---------- audit ----------

def test_each_check_is_audited_with_the_officer(client, demo):
    ids = set(demo["bids"].values())
    events = [
        e for e in client.get("/api/audit/events").json()
        if e["event_type"] == "DOCUMENT_VERIFICATION" and e["bid_id"] in ids
    ]
    by_bidder = {e["bidder_name"]: e for e in events}
    assert set(by_bidder) == {TECHNOVA, APEX, BHARAT, CRESTLINE}
    apex = by_bidder[APEX]
    assert apex["check_status"] == VERIFICATION_FAILED
    assert apex["check_source"] == SOURCE_NAME
    assert apex["document_name"] == "BIS_Certificate.pdf"
    assert apex["requirement_code"] == "REQ-007"
    assert apex["reason"]
    assert (apex["officer_name"], apex["officer_username"]) == (OFFICER_NAME, OFFICER_USERNAME)
    assert client.post("/api/audit/verify").json()["intact"] is True


def test_check_status_is_hashed_and_old_events_still_verify(client, demo, db):
    legacy = append_event(db, "DOCUMENT_LOADED", bidder_name="Legacy Ltd.", document_name="old.pdf")
    db.commit()
    assert legacy.hash == _sha256_json({f: getattr(legacy, f) for f in HASHED_FIELDS})
    assert client.post("/api/audit/verify").json()["intact"] is True

    target = next(
        e for e in client.get("/api/audit/events").json()
        if e["event_type"] == "DOCUMENT_VERIFICATION" and e["check_status"] != "VERIFIED"
    )
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_events SET check_status = 'VERIFIED' WHERE id = :id"), {"id": target["id"]})
    try:
        body = client.post("/api/audit/verify").json()
        assert body["intact"] is False and body["first_broken"]["id"] == target["id"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE audit_events SET check_status = :s WHERE id = :id"),
                         {"s": target["check_status"], "id": target["id"]})
    assert client.post("/api/audit/verify").json()["intact"] is True


# ---------- uploads ----------

def upload(client, tender, name, files):
    resp = client.post(
        f"/api/tenders/{tender}/bids/upload",
        data={"bidder_name": name},
        files=[("files", (fn, data, "application/pdf")) for fn, data in files],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize(
    "filename, status, verdict",
    [
        ("sahyadri_infosystems_bid.pdf", VERIFIED, "PASS"),
        ("vertex_peak_bid.pdf", VERIFICATION_FAILED, "REVIEW"),
        ("northwind_edutech_bid.pdf", UNVERIFIED, "REVIEW"),  # REVIEW already (scan)
    ],
)
def test_uploaded_samples(client, demo, filename, status, verdict):
    bid = upload(client, demo["tender"], filename, [(filename, (SAMPLES / filename).read_bytes())])["bid"]["id"]
    r = _req_result(client.post("/api/evaluations", json={"bid_id": bid}).json())
    assert (r["verification_status"], r["verdict"]) == (status, verdict)


def test_uploaded_vertex_company_mismatch_details(client, demo):
    data = (SAMPLES / "vertex_peak_bid.pdf").read_bytes()
    bid = upload(client, demo["tender"], "Vertex", [("v.pdf", data)])["bid"]["id"]
    r = _req_result(client.post("/api/evaluations", json={"bid_id": bid}).json())
    assert r["verification_details"]["mismatched"][0]["submitted"] == "Arcadia Computing Ltd."
    assert r["verification_details"]["mismatched"][0]["issuer"] == "Summit Ridge Computers Pvt. Ltd."
    assert r["verification_details"]["submitted"]["page"] == 5


# ---------- file re-verification ----------

def _stored_path(doc_name_suffix: str) -> Path:
    return next(p for p in (settings.storage_path / "bids").rglob(f"*_{doc_name_suffix}"))


def test_reverify_detects_a_modified_file(client, demo):
    body = upload(client, demo["tender"], "Reverify Ltd", [("reverify_me.pdf", make_pdf(COMPLIANT_PAGES))])
    bid, doc = body["bid"]["id"], body["documents"][0]["id"]
    url = f"/api/bids/{bid}/documents/{doc}/reverify"

    ok = client.post(url).json()
    assert (ok["status"], ok["label"]) == ("UNCHANGED", "Unchanged since upload")
    assert ok["current_sha256"] == ok["recorded_sha256"]

    path = _stored_path("reverify_me.pdf")
    path.write_bytes(path.read_bytes() + b"\n% appended after upload\n")
    changed = client.post(url).json()
    assert (changed["status"], changed["label"]) == ("CHANGED", "FILE CHANGED SINCE UPLOAD")
    assert changed["current_sha256"] != changed["recorded_sha256"]

    path.unlink()
    assert client.post(url).json()["status"] == "FILE_MISSING"

    doc_out = next(d for d in client.get(f"/api/bids/{bid}/documents").json()["documents"] if d["id"] == doc)
    assert doc_out["last_reverify_status"] == "FILE_MISSING" and doc_out["last_reverified_at"]

    events = [e for e in client.get("/api/audit/events").json() if e["event_type"] == "FILE_REVERIFIED"][-3:]
    assert [e["check_status"] for e in events] == ["UNCHANGED", "CHANGED", "FILE_MISSING"]
    assert all(e["officer_username"] == OFFICER_USERNAME and e["document_id"] == doc for e in events)
    assert client.post("/api/audit/verify").json()["intact"] is True


def test_reviewer_cannot_reverify(client, demo):
    body = upload(client, demo["tender"], "Reviewer Block Ltd", [("r.pdf", make_pdf(COMPLIANT_PAGES))])
    with reviewer_client() as reviewer:
        resp = reviewer.post(f"/api/bids/{body['bid']['id']}/documents/{body['documents'][0]['id']}/reverify")
    assert resp.status_code == 403
    assert "read-only" in resp.json()["detail"]


def test_reverify_rejects_sample_documents_and_wrong_bid(client, demo):
    docs = client.get(f"/api/bids/{demo['bids'][TECHNOVA]}/documents").json()["documents"]
    resp = client.post(f"/api/bids/{demo['bids'][TECHNOVA]}/documents/{docs[0]['id']}/reverify")
    assert resp.status_code == 409
    assert client.post(f"/api/bids/{demo['bids'][APEX]}/documents/{docs[0]['id']}/reverify").status_code == 404


# ---------- signature detection ----------

def signed_pdf() -> bytes:
    doc = pymupdf.open(stream=make_pdf(COMPLIANT_PAGES), filetype="pdf")
    w = pymupdf.Widget()
    w.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
    w.field_name = "BidderSignature"
    w.rect = pymupdf.Rect(72, 700, 272, 750)
    doc[2].add_widget(w)
    return doc.tobytes()


def test_signature_field_detection(client, demo):
    signed = upload(client, demo["tender"], "Signed Ltd", [("signed.pdf", signed_pdf())])
    plain = upload(client, demo["tender"], "Unsigned Ltd", [("plain.pdf", make_pdf(COMPLIANT_PAGES))])
    assert signed["documents"][0]["has_signature_field"] is True
    assert plain["documents"][0]["has_signature_field"] is False


# ---------- red flags ----------

def _flags(client, tender):
    return client.get(f"/api/tenders/{tender}/red-flags").json()


def test_demo_flags_keep_technova_and_bharat_clear(client, demo):
    body = _flags(client, demo["tender"])
    kinds = sorted(f["kind"] for f in body["flags"])
    assert kinds == ["SHARED_CONTACT", "SHARED_CONTACT", "VERIFICATION_MISMATCH"]
    mismatch = next(f for f in body["flags"] if f["kind"] == "VERIFICATION_MISMATCH")
    assert [b["bidder_name"] for b in mismatch["bidders"]] == [APEX]
    assert mismatch["category"] == "DOCUMENT_VERIFICATION"
    assert mismatch["summary"].startswith("Verification failed — officer review required.")
    assert "R-41087632" in mismatch["evidence"][0]["value"] and "R-41087623" in mismatch["evidence"][0]["value"]
    involved = {b["bidder_name"] for f in body["flags"] for b in f["bidders"]}
    assert TECHNOVA not in involved and BHARAT not in involved
    assert body["disclaimer"] == "red flag for review — not proof of wrongdoing"


def test_duplicate_file_flag(client, demo):
    data = make_pdf(COMPLIANT_PAGES)
    upload(client, demo["tender"], "Twin One Ltd", [("one.pdf", data)])
    upload(client, demo["tender"], "Twin Two Ltd", [("two.pdf", data)])
    flags = [f for f in _flags(client, demo["tender"])["flags"] if f["kind"] == "DUPLICATE_FILE"]
    assert len(flags) == 1
    assert {b["bidder_name"] for b in flags[0]["bidders"]} == {"Twin One Ltd", "Twin Two Ltd"}
    assert flags[0]["title"] == "Duplicate file" and flags[0]["category"] == "POSSIBLE_COLLUSION"
    assert all(e["value"].startswith("SHA-256 ") for e in flags[0]["evidence"])


def test_duplicate_certificate_flag(client, demo):
    a = [list(p) for p in COMPLIANT_PAGES]
    b = [list(p) for p in COMPLIANT_PAGES]
    b[0] = ["Covering letter from a different bidder"]  # different bytes, same certificate
    upload(client, demo["tender"], "Cert One Ltd", [("a.pdf", make_pdf(a))])
    upload(client, demo["tender"], "Cert Two Ltd", [("b.pdf", make_pdf(b))])
    body = _flags(client, demo["tender"])
    assert not [f for f in body["flags"] if f["kind"] == "DUPLICATE_FILE"]
    flags = [f for f in body["flags"] if f["kind"] == "DUPLICATE_CERTIFICATE"]
    assert len(flags) == 1
    assert {b["bidder_name"] for b in flags[0]["bidders"]} == {"Cert One Ltd", "Cert Two Ltd"}
    assert {e["value"] for e in flags[0]["evidence"]} == {"R-41234567"}
    assert flags[0]["title"] == "Duplicate certificate number"


# ---------- wording ----------

BANNED = re.compile(r"\b(fake|fraud\w*|forged|forgery|corruption)\b", re.I)


def test_ui_and_api_text_avoid_accusatory_wording(client, demo):
    for path in list((REPO / "frontend" / "src").rglob("*.ts*")) + list((REPO / "backend" / "app").rglob("*.py")):
        assert not BANNED.search(path.read_text(encoding="utf-8")), path
    payloads = [client.get(f"/api/tenders/{demo['tender']}/red-flags").text]
    payloads += [client.get(f"/api/evaluations/{b}/results").text for b in demo["bids"].values()]
    for body in payloads:
        assert not BANNED.search(body)


def test_stale_demo_document_is_refreshed_and_logged_once(client, demo, db):
    from app.models import Document
    from app.seed.loader import load_demo

    doc = (
        db.query(Document)
        .filter(Document.bid_id == demo["bids"][TECHNOVA], Document.original_filename == "BIS_Certificate_Scan.pdf")
        .one()
    )
    stale = dict(doc.fields)
    stale["bis_registration_no"] = {**stale["bis_registration_no"], "value": "R-4119____ (partially legible)"}
    doc.fields = stale
    db.commit()

    before = len(client.get("/api/audit/events").json())
    load_demo(db)
    db.refresh(doc)
    assert doc.fields["bis_registration_no"]["value"] == "R-41190527"
    events = client.get("/api/audit/events").json()
    assert len(events) == before + 1
    assert (events[-1]["event_type"], events[-1]["document_id"]) == ("DOCUMENT_LOADED", doc.id)
    load_demo(db)
    assert len(client.get("/api/audit/events").json()) == before + 1
    assert client.post("/api/audit/verify").json()["intact"] is True
