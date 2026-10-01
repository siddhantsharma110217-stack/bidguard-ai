"""Officer overrides, the hash-chained audit log and document fingerprints."""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.audit import GENESIS_HASH, compute_event_hash, fingerprint_document
from app.db import engine
from app.main import app
from app.models import AuditEvent, Document
from app.seed import sample_data

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REASON = "Original BIS certificate inspected in person; it is valid."


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def demo(client):
    """A freshly loaded and evaluated demo bid for every test."""
    loaded = client.post("/api/demo/load", params={"reset": True}).json()
    resp = client.post("/api/evaluations", json={"bid_id": loaded["bid"]["id"]})
    assert resp.status_code == 201, resp.text
    return {**loaded, "results": resp.json()}


def _req_id(demo, code: str) -> int:
    return next(
        r["requirement_id"] for r in demo["results"]["results"] if r["requirement_code"] == code
    )


def _override(client, demo, code, verdict, reason=REASON, officer="A. Sharma"):
    return client.post(
        f"/api/evaluations/{demo['bid']['id']}/overrides",
        json={
            "requirement_id": _req_id(demo, code),
            "verdict": verdict,
            "reason": reason,
            "officer_name": officer,
        },
    )


# ---------- document fingerprints ----------

def test_documents_are_fingerprinted_on_load(client, demo):
    docs = client.get(f"/api/bids/{demo['bid']['id']}/documents").json()["documents"]
    assert len(docs) == 4
    for d in docs:
        assert SHA256_RE.match(d["sha256"]), d
    assert len({d["sha256"] for d in docs}) == 4


def test_fingerprint_is_deterministic_and_content_sensitive(db, demo):
    doc = db.query(Document).filter(Document.bid_id == demo["bid"]["id"]).first()
    assert fingerprint_document(doc) == doc.sha256

    doc.page_count += 1
    assert fingerprint_document(doc) != doc.sha256
    db.rollback()


def test_fingerprint_hashes_file_bytes_when_present(tmp_path):
    import hashlib

    f = tmp_path / "bid.pdf"
    f.write_bytes(b"%PDF-1.7 sample")
    doc = Document(original_filename="bid.pdf", storage_path=str(f))
    assert fingerprint_document(doc) == hashlib.sha256(b"%PDF-1.7 sample").hexdigest()


def test_document_load_is_recorded_in_audit_log(client, demo):
    events = client.get("/api/audit/events").json()
    loaded = [
        e for e in events
        if e["event_type"] == "DOCUMENT_LOADED" and e["bid_id"] == demo["bid"]["id"]
    ]
    assert {e["document_name"] for e in loaded} == {
        "Technical_Bid.pdf",
        "Warranty_Certificate.pdf",
        "Commercial_Bid.pdf",
        "BIS_Certificate_Scan.pdf",
    }
    docs = client.get(f"/api/bids/{demo['bid']['id']}/documents").json()["documents"]
    by_name = {d["original_filename"]: d["sha256"] for d in docs}
    for e in loaded:
        assert e["document_sha256"] == by_name[e["document_name"]]


# ---------- overrides ----------

def test_override_changes_effective_verdict_and_scores(client, demo):
    before = demo["results"]["summary"]
    resp = _override(client, demo, "REQ-007", "PASS")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    r = next(x for x in body["results"] if x["requirement_code"] == "REQ-007")
    assert r["verdict"] == "PASS"
    assert r["system_verdict"] == "REVIEW"
    assert r["overridden"] is True
    assert r["officer_verdict"] == "PASS"
    assert r["override_reason"] == REASON
    assert r["officer_name"] == "A. Sharma"
    assert r["overridden_at"].endswith("+00:00")
    assert r["score"] == 100.0

    assert body["summary"]["review"] == before["review"] - 1
    assert body["summary"]["passed"] == before["passed"] + 1
    assert body["summary"]["overall_compliance"] == 80.0
    assert body["bid"]["compliance_score"] == 80.0

    # And it is persisted, not just echoed.
    again = client.get(f"/api/evaluations/{demo['bid']['id']}/results").json()
    assert again["summary"] == body["summary"]


def test_override_can_clear_the_gate(client, demo):
    _override(client, demo, "REQ-008", "PASS")
    body = _override(client, demo, "REQ-009", "PASS").json()
    assert body["summary"]["gate_status"] == "RESPONSIVE"
    assert body["summary"]["blocking_requirements"] == 0


def test_override_is_written_to_audit_log(client, demo):
    _override(client, demo, "REQ-008", "REVIEW", officer="  R. Iyer ")
    event = client.get("/api/audit/events").json()[-1]

    assert event["event_type"] == "VERDICT_OVERRIDE"
    assert event["bid_id"] == demo["bid"]["id"]
    assert event["bidder_name"] == "TechNova Systems Pvt. Ltd."
    assert event["requirement_code"] == "REQ-008"
    assert event["requirement_title"]
    assert event["system_verdict"] == "FAIL"
    assert event["officer_verdict"] == "REVIEW"
    assert event["reason"] == REASON
    assert event["officer_name"] == "R. Iyer"
    assert event["timestamp"].endswith("+00:00")
    assert SHA256_RE.match(event["hash"])


@pytest.mark.parametrize(
    "kwargs, status, message",
    [
        ({"reason": "too short"}, 422, "at least 15 characters"),
        ({"reason": "   fourteen ch   "}, 422, "at least 15 characters"),
        ({"officer": "   "}, 422, "officer's name is required"),
        ({"verdict": "MAYBE"}, 422, "verdict must be one of"),
        ({"verdict": "REVIEW"}, 409, "already review"),
    ],
)
def test_override_validation(client, demo, kwargs, status, message):
    events_before = len(client.get("/api/audit/events").json())
    resp = _override(client, demo, "REQ-007", kwargs.pop("verdict", "PASS"), **kwargs)
    assert resp.status_code == status
    assert message in resp.json()["detail"].lower()
    assert len(client.get("/api/audit/events").json()) == events_before


def test_reason_of_exactly_15_characters_is_accepted(client, demo):
    assert _override(client, demo, "REQ-007", "PASS", reason="x" * 15).status_code == 201


def test_override_for_unevaluated_requirement_is_404(client, demo):
    resp = client.post(
        f"/api/evaluations/{demo['bid']['id']}/overrides",
        json={"requirement_id": 999999, "verdict": "PASS", "reason": REASON, "officer_name": "X"},
    )
    assert resp.status_code == 404


def test_reverting_to_system_verdict_withdraws_override(client, demo):
    _override(client, demo, "REQ-007", "PASS")
    body = _override(client, demo, "REQ-007", "REVIEW").json()
    r = next(x for x in body["results"] if x["requirement_code"] == "REQ-007")
    assert r["overridden"] is False
    assert r["verdict"] == "REVIEW"
    assert body["summary"] == demo["results"]["summary"]


def test_override_survives_re_evaluation(client, demo):
    _override(client, demo, "REQ-008", "PASS")
    rerun = client.post("/api/evaluations", json={"bid_id": demo["bid"]["id"]}).json()
    r = next(x for x in rerun["results"] if x["requirement_code"] == "REQ-008")
    assert r["system_verdict"] == "FAIL"
    assert r["verdict"] == "PASS"
    assert r["override_reason"] == REASON


# ---------- chain integrity ----------

def test_chain_links_each_event_to_the_previous_one(client, demo):
    _override(client, demo, "REQ-007", "PASS")
    events = client.get("/api/audit/events").json()
    assert events[0]["prev_hash"] == GENESIS_HASH
    for prev, cur in zip(events, events[1:]):
        assert cur["prev_hash"] == prev["hash"]


def test_verify_reports_intact_chain(client, demo):
    _override(client, demo, "REQ-007", "PASS")
    body = client.post("/api/audit/verify").json()
    assert body["intact"] is True
    assert body["first_broken"] is None
    assert body["verified_events"] == body["total_events"] > 0


def _restore(db, event_id: int, **original):
    sets = ", ".join(f"{k} = :{k}" for k in original)
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE audit_events SET {sets} WHERE id = :id"), {"id": event_id, **original})


def test_editing_an_event_in_the_database_fails_verification(client, demo, db):
    _override(client, demo, "REQ-008", "PASS")
    _override(client, demo, "REQ-009", "PASS")
    events = client.get("/api/audit/events").json()
    target = events[-2]  # not the newest, so later events are still checked
    assert target["requirement_code"] == "REQ-008"

    # Tamper directly in SQLite, bypassing the API and ORM entirely.
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE audit_events SET officer_verdict = 'FAIL' WHERE id = :id"),
            {"id": target["id"]},
        )
    try:
        body = client.post("/api/audit/verify").json()
        assert body["intact"] is False
        assert body["first_broken"]["id"] == target["id"]
        assert body["first_broken"]["position"] == len(events) - 1
        assert body["verified_events"] == len(events) - 2
        assert "modified" in body["first_broken"]["reason"]
    finally:
        _restore(db, target["id"], officer_verdict=target["officer_verdict"])

    assert client.post("/api/audit/verify").json()["intact"] is True


def test_rehashing_an_edited_event_still_breaks_the_next_link(client, demo, db):
    """An attacker who also recomputes the edited event's own hash is caught
    by the following event's prev_hash."""
    _override(client, demo, "REQ-008", "PASS")
    _override(client, demo, "REQ-009", "PASS")
    events = client.get("/api/audit/events").json()
    target, following = events[-2], events[-1]

    row = db.get(AuditEvent, target["id"])
    row.reason = "Forged justification for the change."
    new_hash = compute_event_hash(row)
    db.rollback()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE audit_events SET reason = :r, hash = :h WHERE id = :id"),
            {"r": "Forged justification for the change.", "h": new_hash, "id": target["id"]},
        )
    try:
        body = client.post("/api/audit/verify").json()
        assert body["intact"] is False
        assert body["first_broken"]["id"] == following["id"]
        assert "previous-hash" in body["first_broken"]["reason"].lower()
    finally:
        _restore(db, target["id"], reason=target["reason"], hash=target["hash"])

    assert client.post("/api/audit/verify").json()["intact"] is True


def test_deleting_an_event_fails_verification(client, demo, db):
    _override(client, demo, "REQ-008", "PASS")
    _override(client, demo, "REQ-009", "PASS")
    events = client.get("/api/audit/events").json()
    target, following = events[-2], events[-1]

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": target["id"]})
    try:
        body = client.post("/api/audit/verify").json()
        assert body["intact"] is False
        assert body["first_broken"]["id"] == following["id"]
    finally:
        with engine.begin() as conn:
            cols = ", ".join(target)
            vals = ", ".join(f":{k}" for k in target)
            conn.execute(text(f"INSERT INTO audit_events ({cols}) VALUES ({vals})"), target)

    assert client.post("/api/audit/verify").json()["intact"] is True


def test_audit_log_survives_demo_reset(client, demo):
    _override(client, demo, "REQ-007", "PASS")
    count = len(client.get("/api/audit/events").json())
    client.post("/api/demo/load", params={"reset": True})
    events = client.get("/api/audit/events").json()
    total_docs = sum(len(b["documents"]) for b in sample_data.BIDDERS)
    assert len(events) == count + total_docs  # one DOCUMENT_LOADED per document
    assert client.post("/api/audit/verify").json()["intact"] is True


# ---------- all four demo bidders ----------

BIDDER_NAMES = [b["bidder_name"] for b in sample_data.BIDDERS]


@pytest.fixture()
def all_bids(client):
    """Fresh demo with every bidder evaluated; bidder name -> evaluation results."""
    loaded = client.post("/api/demo/load", params={"reset": True}).json()
    assert [b["bidder_name"] for b in loaded["bids"]] == BIDDER_NAMES
    out = {}
    for bid in loaded["bids"]:
        resp = client.post("/api/evaluations", json={"bid_id": bid["id"]})
        assert resp.status_code == 201, resp.text
        out[bid["bidder_name"]] = resp.json()
    return out


def test_every_bidders_documents_are_fingerprinted_and_logged(client, all_bids):
    events = client.get("/api/audit/events").json()
    seen_hashes = set()
    for name, results in all_bids.items():
        bid_id = results["bid"]["id"]
        docs = client.get(f"/api/bids/{bid_id}/documents").json()["documents"]
        expected = next(b for b in sample_data.BIDDERS if b["bidder_name"] == name)
        assert len(docs) == len(expected["documents"])

        logged = {
            e["document_id"]: e
            for e in events
            if e["event_type"] == "DOCUMENT_LOADED" and e["bid_id"] == bid_id
        }
        assert set(logged) == {d["id"] for d in docs}, name
        for d in docs:
            assert SHA256_RE.match(d["sha256"]), (name, d["original_filename"])
            e = logged[d["id"]]
            assert e["bidder_name"] == name
            assert e["document_name"] == d["original_filename"]
            assert e["document_sha256"] == d["sha256"]
            seen_hashes.add(d["sha256"])

    # Bidders submit same-named files (e.g. Technical_Bid.pdf); their
    # fingerprints must still differ because the contents differ.
    total = sum(len(b["documents"]) for b in sample_data.BIDDERS)
    assert len(seen_hashes) == total


@pytest.mark.parametrize("name", BIDDER_NAMES)
def test_override_and_audit_for_each_bidder(client, all_bids, name):
    results = all_bids[name]
    bid_id = results["bid"]["id"]
    target = results["results"][0]
    new_verdict = "FAIL" if target["verdict"] != "FAIL" else "PASS"

    resp = client.post(
        f"/api/evaluations/{bid_id}/overrides",
        json={
            "requirement_id": target["requirement_id"],
            "verdict": new_verdict,
            "reason": REASON,
            "officer_name": "A. Sharma",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["bid"]["bidder_name"] == name
    r = next(x for x in body["results"] if x["requirement_id"] == target["requirement_id"])
    assert (r["system_verdict"], r["verdict"], r["overridden"]) == (
        target["verdict"], new_verdict, True,
    )

    event = client.get("/api/audit/events").json()[-1]
    assert event["event_type"] == "VERDICT_OVERRIDE"
    assert event["bid_id"] == bid_id
    assert event["bidder_name"] == name
    assert event["requirement_code"] == target["requirement_code"]
    assert event["system_verdict"] == target["verdict"]
    assert event["officer_verdict"] == new_verdict

    # Other bidders are untouched.
    for other, other_results in all_bids.items():
        if other == name:
            continue
        now = client.get(f"/api/evaluations/{other_results['bid']['id']}/results").json()
        assert now["summary"] == other_results["summary"], other
        assert not any(x["overridden"] for x in now["results"])

    assert client.post("/api/audit/verify").json()["intact"] is True


def test_overrides_across_all_bidders_form_one_verifiable_chain(client, all_bids, db):
    for results in all_bids.values():
        target = results["results"][1]
        resp = client.post(
            f"/api/evaluations/{results['bid']['id']}/overrides",
            json={
                "requirement_id": target["requirement_id"],
                "verdict": "REVIEW" if target["verdict"] != "REVIEW" else "PASS",
                "reason": REASON,
                "officer_name": "R. Iyer",
            },
        )
        assert resp.status_code == 201, resp.text

    events = client.get("/api/audit/events").json()
    overrides = [e for e in events if e["event_type"] == "VERDICT_OVERRIDE"][-4:]
    assert [e["bidder_name"] for e in overrides] == BIDDER_NAMES
    assert client.post("/api/audit/verify").json()["intact"] is True

    # Tampering with one bidder's override is pinpointed.
    target = overrides[2]
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE audit_events SET bidder_name = 'Someone Else' WHERE id = :id"),
            {"id": target["id"]},
        )
    try:
        body = client.post("/api/audit/verify").json()
        assert body["intact"] is False
        assert body["first_broken"]["id"] == target["id"]
    finally:
        _restore(db, target["id"], bidder_name=target["bidder_name"])
    assert client.post("/api/audit/verify").json()["intact"] is True
