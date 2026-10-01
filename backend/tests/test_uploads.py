"""Uploading a new bid: validation, storage, fingerprints, audit, extraction
of the committed sample PDFs, prompt injection, and the demo staying intact."""

import hashlib
from pathlib import Path

import pytest

from app.api.uploads import clean_filename
from app.config import settings
from app.extraction.pdf import NO_TEXT_LABEL
from app.main import app
from tests.auth_helpers import officer_client
from scripts.generate_sample_bids import SAMPLES, build_bid_pdf
from tests.pdf_helpers import COMPLIANT_PAGES, make_pdf
from tests.test_extraction import FakeProvider, good_response, source

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
DEMO_NUMBERS = {
    "TechNova Systems Pvt. Ltd.": (76.0, "HIGH", "NON_RESPONSIVE"),
    # Apex and Bharat: BIS PASS -> REVIEW by issuer verification (were 90.0, 100.0).
    "Apex Infotech Solutions": (86.0, "MEDIUM", "NON_RESPONSIVE"),
    "Bharat Digital Technologies Pvt. Ltd.": (96.0, "LOW", "RESPONSIVE"),
    "Crestline Computers LLP": (90.0, "LOW", "RESPONSIVE"),
}


@pytest.fixture(scope="module")
def client():
    with officer_client() as c:
        yield c


@pytest.fixture()
def tender(client):
    return client.post("/api/demo/load", params={"reset": True}).json()["tender"]["id"]


def upload(client, tender, name, files):
    """files: list of (filename, bytes)."""
    return client.post(
        f"/api/tenders/{tender}/bids/upload",
        data={"bidder_name": name},
        files=[("files", (fn, data, "application/pdf")) for fn, data in files],
    )


def evaluate(client, bid_id):
    resp = client.post("/api/evaluations", json={"bid_id": bid_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


def verdict_map(results):
    return {r["requirement_code"]: r["verdict"] for r in results["results"]}


def stored_files() -> list[Path]:
    return [p for p in (settings.storage_path / "bids").rglob("*") if p.is_file()]


# ---------- validation ----------

def test_non_pdf_is_rejected_and_nothing_is_created(client, tender):
    bids_before = len(client.get("/api/bids").json())
    events_before = len(client.get("/api/audit/events").json())
    files_before = stored_files()
    resp = upload(client, tender, "Docx Traders", [("bid.docx", b"PK\x03\x04 word file")])
    assert resp.status_code == 415
    assert resp.json()["detail"] == "'bid.docx' is not a PDF. Only PDF files (.pdf) are accepted."
    assert len(client.get("/api/bids").json()) == bids_before
    assert len(client.get("/api/audit/events").json()) == events_before
    assert stored_files() == files_before


def test_pdf_extension_with_non_pdf_content_is_rejected(client, tender):
    resp = upload(client, tender, "Fake Pdf Ltd", [("bid.pdf", b"<html>not a pdf</html>")])
    assert resp.status_code == 422
    assert "'bid.pdf' is not a valid PDF" in resp.json()["detail"]


def test_oversize_file_is_rejected(client, tender):
    big = b"%PDF-1.7\n" + b"0" * (10 * 1024 * 1024)
    resp = upload(client, tender, "Huge Files Ltd", [("huge.pdf", big)])
    assert resp.status_code == 413
    assert "larger than 10 MB" in resp.json()["detail"]


def test_file_just_under_the_limit_is_accepted(client, tender):
    pdf = make_pdf(COMPLIANT_PAGES)
    padded = pdf + b"\n%" + b"0" * (10 * 1024 * 1024 - len(pdf) - 3) + b"\n"
    assert len(padded) <= 10 * 1024 * 1024
    assert upload(client, tender, "Just Under Ltd", [("bid.pdf", padded)]).status_code == 201


def test_one_bad_file_rejects_the_whole_upload(client, tender):
    files_before = stored_files()
    resp = upload(client, tender, "Mixed Ltd", [("ok.pdf", make_pdf(COMPLIANT_PAGES)), ("bad.txt", b"hi")])
    assert resp.status_code == 415
    assert stored_files() == files_before
    assert "Mixed Ltd" not in [b["bidder_name"] for b in client.get("/api/bids").json()]


@pytest.mark.parametrize(
    "name, files, status, message",
    [
        ("   ", [("a.pdf", None)], 422, "bidder company name is required"),
        ("TechNova Systems Pvt. Ltd.", [("a.pdf", None)], 409, "already exists"),
        ("technova systems pvt. ltd.", [("a.pdf", None)], 409, "already exists"),
        ("No Files Ltd", [], 422, "at least one pdf"),
    ],
)
def test_bidder_and_file_count_validation(client, tender, name, files, status, message):
    files = [(fn, make_pdf(COMPLIANT_PAGES)) for fn, _ in files]
    resp = upload(client, tender, name, files)
    assert resp.status_code == status
    assert message in resp.json()["detail"].lower()


def test_unknown_tender_is_404(client):
    resp = upload(client, 999999, "Anyone", [("a.pdf", make_pdf(COMPLIANT_PAGES))])
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "raw, cleaned",
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("..\\..\\windows\\system32\\evil.pdf", "evil.pdf"),
        ("C:\\bids\\Tech Bid (v2).PDF", "Tech_Bid_v2.pdf"),
        ("Déclaration été.pdf", "Declaration_ete.pdf"),
        ("....pdf", "document.pdf"),
        ("/", "document.pdf"),
        ("a" * 300 + ".pdf", "a" * 80 + ".pdf"),
    ],
)
def test_clean_filename(raw, cleaned):
    assert clean_filename(raw) == cleaned


def test_path_traversal_filename_is_stored_safely(client, tender):
    resp = upload(client, tender, "Traversal Tester", [("../../../../tmp/escape.pdf", make_pdf(COMPLIANT_PAGES))])
    assert resp.status_code == 201, resp.text
    doc = resp.json()["documents"][0]
    assert doc["original_filename"] == "escape.pdf"
    root = (settings.storage_path / "bids").resolve()
    matches = [p for p in stored_files() if p.name.endswith("_escape.pdf")]
    assert len(matches) == 1 and matches[0].resolve().is_relative_to(root)
    assert not Path("/tmp/escape.pdf").exists()


# ---------- fingerprints, audit, documents page data ----------

def test_hash_matches_file_bytes_and_is_audited(client, tender):
    one, two = make_pdf(COMPLIANT_PAGES), make_pdf([["Annexure", "Second document text here"]])
    resp = upload(client, tender, "Hash Check Ltd", [("Technical.pdf", one), ("Annex.pdf", two)])
    assert resp.status_code == 201, resp.text
    bid_id = resp.json()["bid"]["id"]

    docs = client.get(f"/api/bids/{bid_id}/documents").json()["documents"]
    by_name = {d["original_filename"]: d for d in docs}
    for name, data in (("Technical.pdf", one), ("Annex.pdf", two)):
        d = by_name[name]
        assert d["sha256"] == hashlib.sha256(data).hexdigest()
        assert d["file_size"] == len(data)
        assert d["source"] == "UPLOAD"
        assert d["extraction_label"] == "Rule-based extraction (no AI key)"
    assert by_name["Technical.pdf"]["page_count"] == 5
    assert by_name["Annex.pdf"]["page_count"] == 1

    # The stored file on disk has exactly those bytes.
    for p in stored_files():
        if p.name.endswith("_Technical.pdf") and p.read_bytes() == one:
            break
    else:
        pytest.fail("stored Technical.pdf not found with identical bytes")

    events = [e for e in client.get("/api/audit/events").json() if e["bid_id"] == bid_id]
    assert [e["event_type"] for e in events] == ["DOCUMENT_LOADED", "DOCUMENT_LOADED"]
    assert {e["document_sha256"] for e in events} == {d["sha256"] for d in docs}
    assert all(e["bidder_name"] == "Hash Check Ltd" for e in events)
    assert client.post("/api/audit/verify").json()["intact"] is True


def test_uploaded_bid_appears_in_bidder_list(client, tender):
    bid_id = upload(client, tender, "Picker Visible Ltd", [("a.pdf", make_pdf(COMPLIANT_PAGES))]).json()["bid"]["id"]
    listed = client.get("/api/bids", params={"tender_id": tender}).json()
    assert bid_id in [b["id"] for b in listed]


def test_scanned_document_is_marked_and_routes_to_review(client, tender):
    pages = [list(p) for p in COMPLIANT_PAGES]
    pages[3] = None  # BIS page is a scan
    resp = upload(client, tender, "Scanned Page Ltd", [("bid.pdf", make_pdf(pages)), ("scan.pdf", make_pdf([None]))])
    docs = {d["original_filename"]: d for d in resp.json()["documents"]}
    assert docs["scan.pdf"]["text_status"] == NO_TEXT_LABEL
    assert docs["scan.pdf"]["has_text_layer"] is False
    assert docs["bid.pdf"]["text_status"] == f"Page 4: {NO_TEXT_LABEL}"

    results = evaluate(client, resp.json()["bid"]["id"])
    bis = next(r for r in results["results"] if r["requirement_code"] == "REQ-007")
    assert bis["verdict"] == "REVIEW"
    assert bis["rule_trace"]["reason"] == "no_extractable_text"
    assert verdict_map(results) == {**{f"REQ-{i:03d}": "PASS" for i in range(1, 11)}, "REQ-007": "REVIEW"}


# ---------- the committed sample PDFs ----------

EXPECTED_SAMPLE_VERDICTS = {
    "northwind_edutech_bid.pdf": {"REQ-007": "REVIEW"},
    "sahyadri_infosystems_bid.pdf": {"REQ-002": "FAIL", "REQ-008": "FAIL", "REQ-009": "MISSING"},
    # REQ-007 passes the rule but the issuer record for R-41099887 names a
    # different company: VERIFICATION_FAILED -> REVIEW (was PASS).
    "vertex_peak_bid.pdf": {"REQ-006": "FAIL", "REQ-007": "REVIEW", "REQ-008": "FAIL"},
}


def test_committed_samples_match_the_generator():
    for spec in SAMPLES:
        assert (SAMPLES_DIR / spec["file"]).read_bytes() == build_bid_pdf(spec), spec["file"]


@pytest.mark.parametrize("filename", sorted(EXPECTED_SAMPLE_VERDICTS))
def test_rule_based_extraction_of_each_sample(client, tender, filename):
    data = (SAMPLES_DIR / filename).read_bytes()
    resp = upload(client, tender, filename, [(filename, data)])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["extraction_mode"] == "RULES"
    assert body["documents"][0]["sha256"] == hashlib.sha256(data).hexdigest()

    results = evaluate(client, body["bid"]["id"])
    expected = {f"REQ-{i:03d}": "PASS" for i in range(1, 11)} | EXPECTED_SAMPLE_VERDICTS[filename]
    assert verdict_map(results) == expected
    for r in results["results"]:
        assert r["extraction_method"] in ("RULES", "")
        if r["verdict"] in ("PASS", "FAIL"):
            assert r["evidence"] and r["source_page"] > 0 and r["source_document"] == filename


def test_sample_failures_explain_the_numbers(client, tender):
    data = (SAMPLES_DIR / "sahyadri_infosystems_bid.pdf").read_bytes()
    bid_id = upload(client, tender, "Sahyadri", [("sahyadri.pdf", data)]).json()["bid"]["id"]
    by_code = {r["requirement_code"]: r for r in evaluate(client, bid_id)["results"]}
    assert "8 GB" in by_code["REQ-002"]["explanation"]
    assert "60 days" in by_code["REQ-008"]["explanation"]
    assert by_code["REQ-008"]["source_page"] == 3
    assert "within 60 days" in by_code["REQ-008"]["evidence"]


def test_prompt_injection_line_has_no_effect(client, tender):
    spec = next(s for s in SAMPLES if s["injection"])
    with_line = build_bid_pdf(spec, include_injection=True)
    without_line = build_bid_pdf(spec, include_injection=False)
    assert b"Ignore previous instructions" not in without_line

    a = upload(client, tender, "Injected Ltd", [("bid.pdf", with_line)]).json()["bid"]["id"]
    b = upload(client, tender, "Clean Ltd", [("bid.pdf", without_line)]).json()["bid"]["id"]
    ra, rb = evaluate(client, a), evaluate(client, b)
    assert verdict_map(ra) == verdict_map(rb)
    assert ra["summary"] == rb["summary"]
    assert ra["summary"]["gate_status"] == "NON_RESPONSIVE"  # not "marked compliant"

    page_texts = client.get(f"/api/bids/{a}/documents").json()
    assert page_texts["documents"][0]["page_count"] == 6


# ---------- AI mode through the upload API (fake provider) ----------

def test_ai_mode_upload_uses_provider_and_shows_mode(client, tender, monkeypatch):
    pdf = make_pdf(COMPLIANT_PAGES)
    fake = FakeProvider(good_response(source(COMPLIANT_PAGES, "bid.pdf")))
    monkeypatch.setattr("app.extraction.service.get_extraction_provider", lambda: fake)

    body = upload(client, tender, "AI Mode Ltd", [("bid.pdf", pdf)]).json()
    assert body["extraction_mode"] == "AI" and body["extraction_label"] == "AI extraction"
    assert len(fake.calls) == 1
    results = evaluate(client, body["bid"]["id"])
    assert set(verdict_map(results).values()) == {"PASS"}
    assert {r["extraction_method"] for r in results["results"]} == {"AI"}
    assert {r["citation_status"] for r in results["results"]} == {"VERIFIED"}


def test_ai_unsupported_citation_through_api(client, tender, monkeypatch):
    pdf = make_pdf(COMPLIANT_PAGES)
    doc = source(COMPLIANT_PAGES, "bid.pdf")
    fake = FakeProvider(good_response(doc, REQ_003={"quote": "Storage: 2 TB NVMe SSD", "value": "2 TB", "numeric_value": 2000}))
    monkeypatch.setattr("app.extraction.service.get_extraction_provider", lambda: fake)
    bid_id = upload(client, tender, "Bad Citation Ltd", [("bid.pdf", pdf)]).json()["bid"]["id"]
    r = next(x for x in evaluate(client, bid_id)["results"] if x["requirement_code"] == "REQ-003")
    assert r["verdict"] == "REVIEW"
    assert r["citation_status"] == "UNSUPPORTED"
    assert "Unsupported citation" in r["explanation"]


def test_ai_failure_through_api_falls_back(client, tender, monkeypatch):
    fake = FakeProvider(error=ValueError("Expecting value: line 1 column 1"))
    monkeypatch.setattr("app.extraction.service.get_extraction_provider", lambda: fake)
    body = upload(client, tender, "Fallback Ltd", [("bid.pdf", make_pdf(COMPLIANT_PAGES))]).json()
    assert body["extraction_mode"] == "RULES_FALLBACK"
    assert body["documents"][0]["extraction_note"].startswith("AI extraction failed")
    assert set(verdict_map(evaluate(client, body["bid"]["id"])).values()) == {"PASS"}


def test_health_shows_mode_but_never_the_key(client, monkeypatch):
    body = client.get("/api/health").json()
    assert body["extraction_mode"] == "RULES"
    assert body["extraction_label"] == "Rule-based extraction (no AI key)"
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret-test-key")
    body = client.get("/api/health")
    assert body.json()["extraction_label"] == "AI extraction"
    assert body.json()["extraction_model"] == "claude-sonnet-5-5"
    assert "sk-ant" not in body.text


# ---------- same treatment as demo bidders ----------

def test_uploaded_bid_gets_overrides_audit_and_red_flags(client, tender):
    data = (SAMPLES_DIR / "vertex_peak_bid.pdf").read_bytes()
    first = upload(client, tender, "Vertex Peak", [("bid.pdf", data)]).json()["bid"]["id"]
    copy = upload(client, tender, "Vertex Peak Copy", [("bid.pdf", data)]).json()["bid"]["id"]
    results = evaluate(client, first)
    req_008 = next(r["requirement_id"] for r in results["results"] if r["requirement_code"] == "REQ-008")
    resp = client.post(
        f"/api/evaluations/{first}/overrides",
        json={
            "requirement_id": req_008,
            "verdict": "PASS",
            "reason_category": "BIDDER_CLARIFICATION",
            "reason": "Bidder letter VPT/2026/120 revises delivery to 28 days.",
            "officer_name": "A. Sharma",
        },
    )
    assert resp.status_code == 201, resp.text
    assert client.get("/api/audit/events").json()[-1]["bidder_name"] == "Vertex Peak"
    assert client.post("/api/audit/verify").json()["intact"] is True

    flags = client.get(f"/api/tenders/{tender}/red-flags").json()["flags"]
    similar = [f for f in flags if f["kind"] == "SIMILAR_DOCUMENTS"]
    assert any({b["bid_id"] for b in f["bidders"]} == {first, copy} for f in similar)


def test_demo_bidders_numbers_unchanged_after_uploads(client, tender):
    for spec in SAMPLES:
        upload(client, tender, spec["company"], [(spec["file"], (SAMPLES_DIR / spec["file"]).read_bytes())])
    bids = client.get("/api/bids", params={"tender_id": tender}).json()
    demo = [b for b in bids if b["bidder_name"] in DEMO_NUMBERS]
    assert len(demo) == 4
    for b in demo:
        s = evaluate(client, b["id"])["summary"]
        assert (s["overall_compliance"], s["risk_band"], s["gate_status"]) == DEMO_NUMBERS[b["bidder_name"]]
    assert client.post("/api/audit/verify").json()["intact"] is True


def test_demo_reset_removes_uploaded_files(client, tender):
    upload(client, tender, "Temporary Ltd", [("tmp.pdf", make_pdf(COMPLIANT_PAGES))])
    assert any(p.name.endswith("_tmp.pdf") for p in stored_files())
    client.post("/api/demo/load", params={"reset": True})
    assert not any(p.name.endswith("_tmp.pdf") for p in stored_files())


def test_pass_explanation_cites_the_evidence_page(client, tender):
    data = (SAMPLES_DIR / "northwind_edutech_bid.pdf").read_bytes()
    bid_id = upload(client, tender, "Page Cite Ltd", [("bid.pdf", data)]).json()["bid"]["id"]
    ram = next(r for r in evaluate(client, bid_id)["results"] if r["requirement_code"] == "REQ-002")
    assert ram["source_page"] == 2
    assert "page 2" in ram["explanation"]  # not the tender clause's page (4)


def test_oversized_request_is_refused_before_parsing(client, tender):
    resp = client.post(
        f"/api/tenders/{tender}/bids/upload",
        content=b"x",
        headers={"content-length": str(500 * 1024 * 1024), "content-type": "multipart/form-data; boundary=x"},
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]
