"""Tests for the four-bidder demo dataset.

Covers the seed data itself (contact details, the shared phone / bank
account, the two delivery failures), the loader, and the API a reviewing
officer uses to switch between bidders.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Bid, Document, Tender
from app.seed import sample_data
from app.seed.loader import load_demo

TECHNOVA = "TechNova Systems Pvt. Ltd."
APEX = "Apex Infotech Solutions"
BHARAT = "Bharat Digital Technologies Pvt. Ltd."
CRESTLINE = "Crestline Computers LLP"


def _contact_values(bidder: dict) -> dict[str, str]:
    """Contact field -> value for one bidder, across all their documents."""
    found: dict[str, str] = {}
    for doc in bidder["documents"]:
        for field in sample_data.CONTACT_FIELDS:
            if field in doc["fields"]:
                assert field not in found, f"{bidder['bidder_name']} declares {field} twice"
                found[field] = doc["fields"][field]["value"]
    return found


def _bidder(name: str) -> dict:
    return next(b for b in sample_data.BIDDERS if b["bidder_name"] == name)


# ---------- 1. seed data ----------

def test_four_bidders_with_technova_first():
    names = [b["bidder_name"] for b in sample_data.BIDDERS]
    assert names == [TECHNOVA, APEX, BHARAT, CRESTLINE]
    assert sample_data.BIDDER_NAME == TECHNOVA
    assert sample_data.DOCUMENTS is sample_data.BIDDERS[0]["documents"]


@pytest.mark.parametrize("name", [TECHNOVA, APEX, BHARAT, CRESTLINE])
def test_every_bidder_has_complete_contact_details(name):
    contact = _contact_values(_bidder(name))
    assert set(contact) == {"bidder_email", "bidder_phone", "bidder_address", "bank_account"}
    assert all(v.strip() for v in contact.values())
    assert "@" in contact["bidder_email"]


def test_contact_fields_never_collide_with_requirement_fields():
    """Contact details must not be picked up by any compliance rule."""
    rule_fields = {r["rule_params"]["field"] for r in sample_data.REQUIREMENTS}
    assert rule_fields.isdisjoint(sample_data.CONTACT_FIELDS)


@pytest.mark.parametrize("field", ["bidder_phone", "bank_account"])
def test_exactly_apex_and_crestline_share_phone_and_bank_account(field):
    by_value: dict[str, list[str]] = {}
    for b in sample_data.BIDDERS:
        by_value.setdefault(_contact_values(b)[field], []).append(b["bidder_name"])

    shared = [names for names in by_value.values() if len(names) > 1]
    assert shared == [[APEX, CRESTLINE]]


@pytest.mark.parametrize("field", ["bidder_email", "bidder_address"])
def test_emails_and_addresses_are_all_distinct(field):
    values = [_contact_values(b)[field] for b in sample_data.BIDDERS]
    assert len(set(values)) == len(values)


def test_exactly_two_bidders_exceed_the_delivery_limit():
    delivery = {}
    for b in sample_data.BIDDERS:
        [days] = [
            d["fields"]["delivery_days"]["numeric"]
            for d in b["documents"]
            if "delivery_days" in d["fields"]
        ]
        delivery[b["bidder_name"]] = days

    limit = next(r for r in sample_data.REQUIREMENTS if r["code"] == "REQ-008")[
        "rule_params"
    ]["threshold"]
    assert limit == 30
    assert {n: d for n, d in delivery.items() if d > limit} == {TECHNOVA: 45, APEX: 40}


# ---------- 2. loader ----------

def test_loader_adds_missing_bidders_to_an_older_single_bidder_demo(db):
    """A database seeded before this change holds only TechNova; loading again
    must add the other three without touching the existing bid."""
    load_demo(db, reset=True)
    tender = (
        db.query(Tender)
        .filter(Tender.reference_no == sample_data.TENDER["reference_no"])
        .one()
    )
    for bid in db.query(Bid).filter(Bid.tender_id == tender.id, Bid.bidder_name != TECHNOVA):
        db.delete(bid)
    db.commit()
    technova_id = db.query(Bid).filter(Bid.tender_id == tender.id).one().id

    _, bids = load_demo(db)

    assert [b.bidder_name for b in bids] == [TECHNOVA, APEX, BHARAT, CRESTLINE]
    assert bids[0].id == technova_id
    assert db.query(Bid).filter(Bid.tender_id == tender.id).count() == 4
    for bid, bidder in zip(bids, sample_data.BIDDERS):
        count = db.query(Document).filter(Document.bid_id == bid.id).count()
        assert count == len(bidder["documents"])


# ---------- 3. API ----------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def demo(client):
    resp = client.post("/api/demo/load", params={"reset": True})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(scope="module")
def bid_ids(demo) -> dict[str, int]:
    return {b["bidder_name"]: b["id"] for b in demo["bids"]}


def test_demo_load_returns_all_four_bids(demo):
    assert demo["bidder_count"] == 4
    assert [b["bidder_name"] for b in demo["bids"]] == [TECHNOVA, APEX, BHARAT, CRESTLINE]
    assert demo["bid"] == demo["bids"][0]
    assert all(b["tender_id"] == demo["tender"]["id"] for b in demo["bids"])


def test_demo_reload_does_not_duplicate_bids(client, demo):
    again = client.post("/api/demo/load").json()
    assert [b["id"] for b in again["bids"]] == [b["id"] for b in demo["bids"]]

    bids = client.get("/api/bids", params={"tender_id": demo["tender"]["id"]}).json()
    names = [b["bidder_name"] for b in bids]
    assert names == [TECHNOVA, APEX, BHARAT, CRESTLINE]


def test_bids_can_be_filtered_by_tender(client, demo):
    other = client.post("/api/tenders", json={"title": "Unrelated Tender"}).json()
    client.post("/api/bids", json={"tender_id": other["id"], "bidder_name": "Elsewhere Ltd."})

    scoped = client.get("/api/bids", params={"tender_id": demo["tender"]["id"]}).json()
    assert {b["tender_id"] for b in scoped} == {demo["tender"]["id"]}
    assert "Elsewhere Ltd." not in {b["bidder_name"] for b in scoped}

    everything = client.get("/api/bids").json()
    assert "Elsewhere Ltd." in {b["bidder_name"] for b in everything}


def test_dashboard_lists_every_demo_bid(client, demo, bid_ids):
    body = client.get("/api/dashboard").json()
    assert body["demo_bid_id"] == bid_ids[TECHNOVA]
    assert body["demo_bid_ids"] == [bid_ids[n] for n in (TECHNOVA, APEX, BHARAT, CRESTLINE)]


@pytest.mark.parametrize(
    "name, expected_contact",
    [
        (TECHNOVA, {"bidder_phone": "+91 80 4718 2290"}),
        (APEX, {"bidder_email": "bids@apexinfotech.co.in"}),
        (BHARAT, {"bidder_email": "procurement@bharatdigital.in"}),
        (CRESTLINE, {"bidder_email": "sales@crestlinecomputers.in"}),
    ],
)
def test_documents_endpoint_returns_contact_details(client, bid_ids, name, expected_contact):
    body = client.get(f"/api/bids/{bid_ids[name]}/documents").json()

    assert body["bid"]["bidder_name"] == name
    assert [c["field"] for c in body["contact"]] == list(sample_data.CONTACT_FIELDS)
    assert [c["label"] for c in body["contact"]] == list(sample_data.CONTACT_FIELDS.values())
    for c in body["contact"]:
        assert c["source_document"] == "Commercial_Bid.pdf"
        assert c["source_page"] == 1
        assert c["value"]

    values = {c["field"]: c["value"] for c in body["contact"]}
    for field, value in expected_contact.items():
        assert values[field] == value


def test_apex_and_crestline_show_the_same_phone_and_bank_account(client, bid_ids):
    def contact(name):
        body = client.get(f"/api/bids/{bid_ids[name]}/documents").json()
        return {c["field"]: c["value"] for c in body["contact"]}

    apex, crestline = contact(APEX), contact(CRESTLINE)
    assert apex["bidder_phone"] == crestline["bidder_phone"]
    assert apex["bank_account"] == crestline["bank_account"]
    assert apex["bidder_email"] != crestline["bidder_email"]
    assert apex["bidder_address"] != crestline["bidder_address"]


def test_each_bid_only_sees_its_own_documents(client, bid_ids):
    for name in (TECHNOVA, APEX, BHARAT, CRESTLINE):
        body = client.get(f"/api/bids/{bid_ids[name]}/documents").json()
        assert body["total"] == len(_bidder(name)["documents"])


# ---------- 4. per-bidder evaluation ----------

@pytest.fixture(scope="module")
def evaluations(client, bid_ids) -> dict[str, dict]:
    out = {}
    for name, bid_id in bid_ids.items():
        resp = client.post("/api/evaluations", json={"bid_id": bid_id})
        assert resp.status_code == 201, resp.text
        out[name] = resp.json()
    return out


@pytest.mark.parametrize(
    "name, counts, compliance, risk, band, gate",
    [
        (TECHNOVA, (7, 1, 1, 1), 76.0, 53.0, "HIGH", "NON_RESPONSIVE"),
        (APEX, (9, 0, 1, 0), 90.0, 25.0, "MEDIUM", "NON_RESPONSIVE"),
        (BHARAT, (10, 0, 0, 0), 100.0, 0.0, "LOW", "RESPONSIVE"),
        (CRESTLINE, (9, 0, 0, 1), 90.0, 20.0, "LOW", "RESPONSIVE"),
    ],
)
def test_bidder_summary(evaluations, name, counts, compliance, risk, band, gate):
    result = evaluations[name]
    s = result["summary"]

    assert result["bid"]["bidder_name"] == name
    assert (s["passed"], s["review"], s["failed"], s["missing"]) == counts
    assert s["overall_compliance"] == compliance
    assert s["risk_score"] == risk
    assert s["risk_band"] == band
    assert s["gate_status"] == gate


@pytest.mark.parametrize(
    "name, verdict, observed",
    [(TECHNOVA, "FAIL", 45), (APEX, "FAIL", 40), (BHARAT, "PASS", 21), (CRESTLINE, "PASS", 28)],
)
def test_delivery_verdict_per_bidder(evaluations, name, verdict, observed):
    delivery = next(
        r for r in evaluations[name]["results"] if r["requirement_code"] == "REQ-008"
    )
    assert delivery["verdict"] == verdict
    assert delivery["rule_trace"]["observed"] == observed
    assert delivery["rule_trace"]["required_maximum"] == 30
    if verdict == "FAIL":
        assert str(observed) in delivery["explanation"]


def test_crestline_missing_energy_rating_is_non_blocking(evaluations):
    """Crestline's own package has no energy rating; another bidder's document
    must never be used to fill the gap."""
    energy = next(
        r for r in evaluations[CRESTLINE]["results"] if r["requirement_code"] == "REQ-010"
    )
    assert energy["verdict"] == "MISSING"
    assert energy["obligation"] == "DESIRABLE"
    assert energy["source_document_id"] is None
    assert evaluations[CRESTLINE]["summary"]["blocking_requirements"] == 0


def test_results_are_stored_per_bid(client, evaluations, bid_ids):
    for name, bid_id in bid_ids.items():
        stored = client.get(f"/api/evaluations/{bid_id}/results").json()
        assert stored["bid"]["bidder_name"] == name
        assert stored["summary"] == evaluations[name]["summary"]
