"""Contact details of uploaded bids and the Red Flags they produce."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.extraction.pdf import read_pdf
from app.extraction.rules import SourceDoc, extract_contacts
from app.extraction.service import extract_bid
from app.main import app
from app.redflags import normalize_contact
from scripts.generate_sample_bids import APEX_SHARED_PHONE, SHARED_ACCOUNT
from tests.pdf_helpers import COMPLIANT_PAGES, demo_requirements, make_pdf
from tests.test_extraction import FakeProvider, good_response

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
TECHNOVA = "TechNova Systems Pvt. Ltd."
APEX = "Apex Infotech Solutions"
BHARAT = "Bharat Digital Technologies Pvt. Ltd."
CRESTLINE = "Crestline Computers LLP"
NORTHWIND = "Northwind Edutech Systems Pvt. Ltd."
SAHYADRI = "Sahyadri Infosystems LLP"
VERTEX = "Vertex Peak Technologies Pvt. Ltd."
UPLOADS = {
    NORTHWIND: "northwind_edutech_bid.pdf",
    SAHYADRI: "sahyadri_infosystems_bid.pdf",
    VERTEX: "vertex_peak_bid.pdf",
}


def sample_doc(filename: str) -> SourceDoc:
    text = read_pdf((SAMPLES_DIR / filename).read_bytes())
    return SourceDoc(filename, text.pages, text.pages_without_text)


def contacts(docs: list[SourceDoc]) -> dict[str, dict]:
    return {k: data for k, (_, data) in extract_contacts(docs).items()}


# ---------- extraction from the sample PDFs ----------

EXPECTED = {
    "northwind_edutech_bid.pdf": {
        "bidder_phone": ("+91-98110-36524", 1),
        "bidder_email": ("tenders@northwind-edutech.example.in", 1),
        "bidder_address": ("Plot 21, Electronic City Phase I, Bengaluru, Karnataka 560100", 3),
        "bank_account": ("Kotak Mahindra Bank, A/c No. 7712049935, IFSC KKBK0008061", 3),
    },
    "sahyadri_infosystems_bid.pdf": {
        "bidder_phone": ("+91 20 6712 4410", 1),
        "bidder_email": ("bids@sahyadri-infosystems.example.in", 1),
        "bidder_address": ("Office 404, Baner Business Bay, Baner Road, Pune, Maharashtra 411045", 3),
        "bank_account": ("HDFC Bank, A/c No. 50100234567812, IFSC HDFC0001234", 3),
    },
    "vertex_peak_bid.pdf": {
        "bidder_phone": ("+91 172 470 8813", 1),
        "bidder_email": ("contracts@vertexpeak.example.in", 1),
        "bidder_address": ("SCO 112, Sector 17-C, Chandigarh 160017", 3),
        "bank_account": ("HDFC Bank, A/c No. 50100234567812, IFSC HDFC0001234", 3),
    },
}


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_contacts_extracted_from_each_sample(filename):
    found = contacts([sample_doc(filename)])
    assert {k: (d["value"], d["page"]) for k, d in found.items()} == EXPECTED[filename]
    for data in found.values():
        assert data["snippet"] and data["extraction_method"] == "RULES"
        assert data["confidence"] >= 0.9


def test_bank_account_keeps_account_number_and_ifsc_separately():
    bank = contacts([sample_doc("sahyadri_infosystems_bid.pdf")])["bank_account"]
    assert bank["account_number"] == SHARED_ACCOUNT
    assert bank["ifsc"] == "HDFC0001234"  # found on its own line on the same page


def test_contacts_only_from_cover_and_commercial_pages():
    pages = [
        ["Covering letter", "Phone: +91 80 1111 2222", "Email: bids@bidder.example.in"],
        ["Annexure C: Warranty Certificate", "OEM helpdesk Phone: +91 22 9999 8888",
         "Email: support@oem.example.com"],
        ["Technical compliance", "Support Email: noc@bidder.example.in"],
        ["Commercial terms", "Registered Office: 5 MG Road, Bengaluru 560001",
         "Bank Name: Axis Bank", "Account No.: 912010045678123, IFSC: UTIB0000009"],
    ]
    found = contacts([SourceDoc("bid.pdf", read_pdf(make_pdf(pages)).pages, [])])
    assert found["bidder_phone"]["value"] == "+91 80 1111 2222"
    assert found["bidder_email"]["value"] == "bids@bidder.example.in"
    assert found["bidder_address"]["page"] == 4
    assert found["bank_account"]["value"] == "Axis Bank, A/c No. 912010045678123, IFSC UTIB0000009"


def test_separate_manufacturer_letter_is_not_the_bidders_contact():
    bid = SourceDoc("Technical_Bid.pdf", read_pdf(make_pdf([["Technical details only"]])).pages, [])
    maf = SourceDoc(
        "MAF.pdf",
        read_pdf(make_pdf([["Manufacturer Authorization Form", "Phone: +91 44 7777 6666"]])).pages,
        [],
    )
    assert contacts([bid, maf]) == {}


def test_numbers_without_a_phone_label_are_not_phones():
    pages = [["Covering letter", "Bid No. 2026004471902 dated 10-03-2026", "Quantity: 250 units"]]
    assert "bidder_phone" not in contacts([SourceDoc("c.pdf", read_pdf(make_pdf(pages)).pages, [])])


def test_contacts_are_extracted_in_ai_mode_too():
    pages = [["Covering letter", "Phone: +91 80 1111 2222"], *COMPLIANT_PAGES[1:]]
    doc = SourceDoc("bid.pdf", read_pdf(make_pdf(pages)).pages, [])
    result = extract_bid(demo_requirements(), [doc], provider=FakeProvider(good_response(doc)))
    assert result.mode == "AI"
    assert result.fields["bidder_phone"][1]["value"] == "+91 80 1111 2222"


# ---------- normalised matching ----------

@pytest.mark.parametrize(
    "field, a, b",
    [
        ("bidder_phone", APEX_SHARED_PHONE, "+91 98110 36524"),
        ("bidder_phone", "+91-98110-36524", "098110 36524"),
        ("bank_account", "HDFC Bank, A/c No. 50100234567812, IFSC HDFC0001234",
         "Account Number: 50100234567812"),
        ("bidder_email", "Bids@Example.IN", "bids@example.in"),
    ],
)
def test_sample_formats_normalise_to_the_same_value(field, a, b):
    assert normalize_contact(field, a) == normalize_contact(field, b)


def test_distinct_sample_values_do_not_match():
    a = EXPECTED["northwind_edutech_bid.pdf"]["bank_account"][0]
    b = EXPECTED["sahyadri_infosystems_bid.pdf"]["bank_account"][0]
    assert normalize_contact("bank_account", a) != normalize_contact("bank_account", b)


# ---------- live Red Flags with uploaded bids ----------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def flags(client):
    tender = client.post("/api/demo/load", params={"reset": True}).json()["tender"]["id"]
    for name, filename in UPLOADS.items():
        resp = client.post(
            f"/api/tenders/{tender}/bids/upload",
            data={"bidder_name": name},
            files=[("files", (filename, (SAMPLES_DIR / filename).read_bytes(), "application/pdf"))],
        )
        assert resp.status_code == 201, resp.text
    body = client.get(f"/api/tenders/{tender}/red-flags").json()
    return {**body, "tender_id": tender}


def _groups(body, title):
    return [{b["bidder_name"] for b in f["bidders"]} for f in body["flags"] if f["title"] == title]


def test_uploaded_bid_sharing_apex_phone_is_flagged(flags):
    assert _groups(flags, "Shared phone") == [{APEX, CRESTLINE, NORTHWIND}]
    flag = next(f for f in flags["flags"] if f["title"] == "Shared phone")
    northwind = next(e for e in flag["evidence"] if e["bidder_name"] == NORTHWIND)
    assert northwind["value"] == "+91-98110-36524"
    assert northwind["source_document"] == "northwind_edutech_bid.pdf"
    assert northwind["source_page"] == 1


def test_two_uploaded_bids_sharing_a_bank_account_are_flagged(flags):
    groups = _groups(flags, "Shared bank account")
    assert {SAHYADRI, VERTEX} in groups
    assert {APEX, CRESTLINE} in groups  # the existing demo flag is unchanged
    assert len(groups) == 2
    flag = next(
        f for f in flags["flags"]
        if f["title"] == "Shared bank account" and {b["bidder_name"] for b in f["bidders"]} == {SAHYADRI, VERTEX}
    )
    assert {e["source_page"] for e in flag["evidence"]} == {3}
    assert all(f["category"] == "POSSIBLE_COLLUSION" for f in flags["flags"])


def test_exactly_the_intended_flags_and_technova_bharat_stay_clean(flags):
    assert flags["total_flags"] == 3
    assert sorted(f["title"] for f in flags["flags"]) == [
        "Shared bank account", "Shared bank account", "Shared phone",
    ]
    involved = {b["bidder_name"] for f in flags["flags"] for b in f["bidders"]}
    assert TECHNOVA not in involved and BHARAT not in involved
    # The three samples come from one template but stay under the 90%
    # similarity threshold: no document-similarity flags.
    assert not [f for f in flags["flags"] if f["kind"] == "SIMILAR_DOCUMENTS"]


def test_uploaded_contacts_shown_like_demo_contacts(client, flags):
    bids = client.get("/api/bids", params={"tender_id": flags["tender_id"]}).json()
    bid_id = next(b["id"] for b in bids if b["bidder_name"] == SAHYADRI)
    contact = client.get(f"/api/bids/{bid_id}/documents").json()["contact"]
    by_field = {c["field"]: c for c in contact}
    assert set(by_field) == {"bidder_email", "bidder_phone", "bidder_address", "bank_account"}
    assert by_field["bank_account"]["label"] == "Bank Account"
    assert by_field["bank_account"]["source_page"] == 3
    assert by_field["bidder_phone"]["source_document"] == "sahyadri_infosystems_bid.pdf"


def test_contact_fields_do_not_change_verdicts(client, flags):
    bids = client.get("/api/bids", params={"tender_id": flags["tender_id"]}).json()
    bid_id = next(b["id"] for b in bids if b["bidder_name"] == NORTHWIND)
    results = client.post("/api/evaluations", json={"bid_id": bid_id}).json()
    assert len(results["results"]) == 10
    assert results["summary"]["passed"] == 9 and results["summary"]["review"] == 1
