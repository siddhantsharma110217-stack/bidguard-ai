"""Officer login: passwords, tokens, route protection, roles, and the
officer identity on overrides and audit events."""

import base64
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.audit import HASHED_FIELDS, _sha256_json, append_event
from app.auth import (
    DEMO_USERS,
    InvalidToken,
    create_token,
    hash_password,
    read_token,
    seed_password,
    seed_users,
    verify_password,
)
from app.config import settings
from app.db import engine
from app.main import app
from app.models import User
from tests.auth_helpers import (
    OFFICER,
    OFFICER_NAME,
    OFFICER_USERNAME,
    REVIEWER,
    SECOND_OFFICER,
    auth_headers,
    client_as,
    officer_client,
    reviewer_client,
)
from tests.pdf_helpers import COMPLIANT_PAGES, make_pdf

REASON = "Bidder letter TN/2026/118 confirms 30-day delivery."


@pytest.fixture(scope="module")
def anon():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def officer():
    with officer_client() as c:
        yield c


@pytest.fixture(scope="module")
def reviewer():
    with reviewer_client() as c:
        yield c


@pytest.fixture()
def demo(officer):
    loaded = officer.post("/api/demo/load", params={"reset": True}).json()
    bid = loaded["bid"]["id"]
    results = officer.post("/api/evaluations", json={"bid_id": bid}).json()
    req = next(r["requirement_id"] for r in results["results"] if r["requirement_code"] == "REQ-008")
    return {"tender": loaded["tender"]["id"], "bid": bid, "req_008": req}


def override_body(demo, **extra):
    return {
        "requirement_id": demo["req_008"],
        "verdict": "PASS",
        "reason_category": "BIDDER_CLARIFICATION",
        "reason": REASON,
        **extra,
    }


# ---------- login ----------

def test_login_success_returns_token_and_user(anon):
    resp = anon.post("/api/auth/login", json={"username": "asharma", "password": seed_password(OFFICER)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"] == {
        "username": "asharma",
        "full_name": "Anita Sharma",
        "designation": "Evaluation Officer",
        "role": "OFFICER",
    }
    assert body["expires_at"] > time.time()
    me = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200 and me.json()["username"] == "asharma"


def test_login_username_is_case_insensitive(anon):
    resp = anon.post("/api/auth/login", json={"username": "  ASharma ", "password": seed_password(OFFICER)})
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "username, password",
    [
        ("asharma", "wrong-password"),
        ("asharma", ""),
        ("nobody", "officer-demo-1"),
        ("asharma", "OFFICER-DEMO-1"),
    ],
)
def test_login_failure_is_401_with_one_message(anon, username, password):
    resp = anon.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password."
    assert "token" not in resp.text


def test_reviewer_and_second_officer_can_log_in(anon):
    for user in (REVIEWER, SECOND_OFFICER):
        resp = anon.post("/api/auth/login", json={"username": user.username, "password": seed_password(user)})
        assert resp.json()["user"]["role"] == user.role


# ---------- tokens ----------

def test_expired_token_is_rejected(anon):
    token, _ = create_token("asharma", ttl_seconds=-1)
    resp = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"]


def _forge_payload(token: str, **changes) -> str:
    payload, sig = token.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    data.update(changes)
    forged = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).rstrip(b"=").decode()
    return f"{forged}.{sig}"


@pytest.mark.parametrize(
    "tamper",
    [
        lambda t: _forge_payload(t, sub="riyer"),  # impersonate another officer
        lambda t: _forge_payload(t, exp=int(time.time()) + 10**8),  # extend expiry
        lambda t: t[:-2] + ("AA" if not t.endswith("AA") else "BB"),  # alter signature
        lambda t: t.split(".")[0],  # drop the signature
        lambda t: "not-a-token",
    ],
    ids=["swap-user", "extend-expiry", "bad-signature", "no-signature", "garbage"],
)
def test_tampered_token_is_rejected(anon, tamper):
    token, _ = create_token("asharma")
    resp = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {tamper(token)}"})
    assert resp.status_code == 401
    assert "not valid" in resp.json()["detail"]


def test_token_signed_with_another_secret_is_rejected(anon, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "some-other-secret")
    token, _ = create_token("asharma")
    monkeypatch.undo()
    with pytest.raises(InvalidToken):
        read_token(token)
    assert anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_for_unknown_user_is_rejected(anon):
    token, _ = create_token("ghost")
    assert anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("header", ["", "Bearer", "Basic abc", "Token xyz"])
def test_missing_or_wrong_scheme_is_401(anon, header):
    headers = {"Authorization": header} if header else {}
    resp = anon.get("/api/bids", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Please log in to continue." or "not valid" in resp.json()["detail"]


# ---------- route protection ----------

PROTECTED = [
    ("GET", "/api/dashboard"),
    ("GET", "/api/tenders"),
    ("GET", "/api/tenders/1"),
    ("GET", "/api/tenders/1/requirements"),
    ("GET", "/api/tenders/1/red-flags"),
    ("POST", "/api/tenders/1/bids/upload"),
    ("POST", "/api/tenders"),
    ("GET", "/api/bids"),
    ("POST", "/api/bids"),
    ("GET", "/api/bids/1"),
    ("GET", "/api/bids/1/documents"),
    ("POST", "/api/evaluations"),
    ("GET", "/api/evaluations/1"),
    ("GET", "/api/evaluations/1/results"),
    ("POST", "/api/evaluations/1/overrides"),
    ("GET", "/api/audit/events"),
    ("POST", "/api/audit/verify"),
    ("GET", "/api/auth/me"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_unauthenticated_requests_are_rejected(anon, method, path):
    resp = anon.request(method, path, json={})
    assert resp.status_code == 401, (method, path, resp.status_code)


def test_every_api_route_is_covered_by_the_protection_test():
    public = {
        ("POST", "/api/auth/login"),
        ("GET", "/api/auth/demo-accounts"),
        ("GET", "/api/health"),
        ("POST", "/api/demo/load"),
    }
    # Every API operation the app exposes, from its OpenAPI schema.
    routes = {
        (method.upper(), path)
        for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api")
        for method in ops
    }
    normalised = {(m, p.replace("{tender_id}", "1").replace("{bid_id}", "1")) for m, p in routes}
    assert normalised - public == set(PROTECTED)


def test_public_routes_need_no_token(anon):
    assert anon.get("/api/health").status_code == 200
    assert anon.post("/api/demo/load").status_code == 200
    assert anon.get("/api/auth/demo-accounts").status_code == 200


# ---------- roles ----------

def test_reviewer_can_view_everything(reviewer, demo):
    for path in (
        f"/api/evaluations/{demo['bid']}/results",
        f"/api/bids/{demo['bid']}/documents",
        f"/api/tenders/{demo['tender']}/red-flags",
        "/api/audit/events",
        "/api/dashboard",
    ):
        assert reviewer.get(path).status_code == 200, path
    assert reviewer.post("/api/audit/verify").status_code == 200


def test_reviewer_is_blocked_from_overriding(reviewer, officer, demo):
    events_before = len(officer.get("/api/audit/events").json())
    resp = reviewer.post(f"/api/evaluations/{demo['bid']}/overrides", json=override_body(demo))
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert "Kavita Menon" in detail and "REVIEWER" in detail and "read-only" in detail
    assert len(officer.get("/api/audit/events").json()) == events_before
    results = officer.get(f"/api/evaluations/{demo['bid']}/results").json()
    assert not any(r["overridden"] for r in results["results"])


def test_reviewer_is_blocked_from_cancelling_an_override(reviewer, officer, demo):
    assert officer.post(f"/api/evaluations/{demo['bid']}/overrides", json=override_body(demo)).status_code == 201
    revert = override_body(demo, verdict="FAIL")
    assert reviewer.post(f"/api/evaluations/{demo['bid']}/overrides", json=revert).status_code == 403


def test_reviewer_is_blocked_from_uploading(reviewer, officer, demo):
    bids_before = len(officer.get("/api/bids").json())
    resp = reviewer.post(
        f"/api/tenders/{demo['tender']}/bids/upload",
        data={"bidder_name": "Reviewer Upload Ltd"},
        files=[("files", ("bid.pdf", make_pdf(COMPLIANT_PAGES), "application/pdf"))],
    )
    assert resp.status_code == 403
    assert "read-only" in resp.json()["detail"]
    assert len(officer.get("/api/bids").json()) == bids_before


def test_reviewer_cannot_create_bids_or_tenders(reviewer, demo):
    assert reviewer.post("/api/bids", json={"tender_id": demo["tender"], "bidder_name": "X"}).status_code == 403
    assert reviewer.post("/api/tenders", json={"title": "X"}).status_code == 403


# ---------- officer identity comes from the session ----------

def test_override_uses_session_name_not_the_request(officer, demo):
    resp = officer.post(
        f"/api/evaluations/{demo['bid']}/overrides",
        json=override_body(demo, officer_name="Someone Else", officer_username="kmenon"),
    )
    assert resp.status_code == 201, resp.text
    r = next(x for x in resp.json()["results"] if x["requirement_id"] == demo["req_008"])
    assert (r["officer_name"], r["officer_username"]) == (OFFICER_NAME, OFFICER_USERNAME)
    event = officer.get("/api/audit/events").json()[-1]
    assert event["officer_name"] == "Anita Sharma"
    assert event["officer_username"] == "asharma"


def test_each_officer_is_recorded_under_their_own_name(demo):
    with client_as(SECOND_OFFICER.username) as rahul:
        resp = rahul.post(f"/api/evaluations/{demo['bid']}/overrides", json=override_body(demo))
        assert resp.status_code == 201
        event = rahul.get("/api/audit/events").json()[-1]
    assert (event["officer_name"], event["officer_username"]) == ("Rahul Iyer", "riyer")


def test_blank_officer_name_in_request_is_irrelevant(officer, demo):
    resp = officer.post(f"/api/evaluations/{demo['bid']}/overrides", json=override_body(demo, officer_name="   "))
    assert resp.status_code == 201


# ---------- passwords ----------

def test_passwords_are_stored_only_as_salted_hashes(db):
    users = db.query(User).all()
    assert {u.username for u in users} >= {u.username for u in DEMO_USERS}
    passwords = [seed_password(u) for u in DEMO_USERS]
    for user in users:
        assert user.password_hash.startswith("scrypt$")
        for pw in passwords:
            assert pw not in user.password_hash
    # Nothing in any column of the users table is a plaintext password.
    with engine.connect() as conn:
        for row in conn.execute(text("SELECT * FROM users")):
            for value in row:
                assert str(value) not in passwords


def test_same_password_gets_a_different_salt():
    a, b = hash_password("same-password"), hash_password("same-password")
    assert a != b
    assert verify_password("same-password", a) and verify_password("same-password", b)
    assert not verify_password("other", a)
    assert not verify_password("same-password", "plaintext-not-a-hash")


def test_password_from_environment_is_rehashed_on_seed(db, anon, monkeypatch):
    monkeypatch.setattr(settings, "demo_officer2_password", "rotated-password-123")
    seed_users(db)
    ok = anon.post("/api/auth/login", json={"username": "riyer", "password": "rotated-password-123"})
    old = anon.post("/api/auth/login", json={"username": "riyer", "password": "officer-demo-2"})
    assert ok.status_code == 200 and old.status_code == 401
    monkeypatch.undo()
    seed_users(db)
    assert anon.post("/api/auth/login", json={"username": "riyer", "password": "officer-demo-2"}).status_code == 200


def test_demo_accounts_listed_only_in_demo_mode(anon, monkeypatch):
    accounts = anon.get("/api/auth/demo-accounts").json()
    assert [(a["username"], a["role"]) for a in accounts] == [
        ("asharma", "OFFICER"), ("riyer", "OFFICER"), ("kmenon", "REVIEWER"),
    ]
    assert all(a["demo_password"] for a in accounts)

    # A password changed through the environment is never published.
    monkeypatch.setattr(settings, "demo_reviewer_password", "private-password")
    accounts = anon.get("/api/auth/demo-accounts").json()
    assert next(a for a in accounts if a["username"] == "kmenon")["demo_password"] is None
    assert "private-password" not in anon.get("/api/auth/demo-accounts").text

    monkeypatch.setattr(settings, "demo_mode", False)
    assert anon.get("/api/auth/demo-accounts").json() == []


def test_health_does_not_expose_secrets(anon):
    body = anon.get("/api/health").text
    assert settings.session_secret not in body
    assert all(seed_password(u) not in body for u in DEMO_USERS)


# ---------- audit chain with old and new events ----------

def test_events_without_username_hash_as_before_and_chain_verifies(officer, demo, db):
    legacy = append_event(
        db, "VERDICT_OVERRIDE", bidder_name="Legacy Ltd.", reason=REASON,
        officer_name="Old Officer", reason_category="OTHER",
    )
    db.commit()
    # Hash of an event with no username is exactly the pre-login hash.
    content = {f: getattr(legacy, f) for f in HASHED_FIELDS}
    content["reason_category"] = "OTHER"
    assert legacy.hash == _sha256_json(content)

    assert officer.post(f"/api/evaluations/{demo['bid']}/overrides", json=override_body(demo)).status_code == 201
    new = officer.get("/api/audit/events").json()[-1]
    assert new["officer_username"] == "asharma"
    assert officer.post("/api/audit/verify").json()["intact"] is True


def test_officer_username_is_part_of_the_hash(officer, demo, db):
    assert officer.post(f"/api/evaluations/{demo['bid']}/overrides", json=override_body(demo)).status_code == 201
    event = officer.get("/api/audit/events").json()[-1]
    for forged in ("riyer", ""):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE audit_events SET officer_username = :u WHERE id = :id"),
                {"u": forged, "id": event["id"]},
            )
        try:
            body = officer.post("/api/audit/verify").json()
            assert body["intact"] is False and body["first_broken"]["id"] == event["id"]
        finally:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE audit_events SET officer_username = :u WHERE id = :id"),
                    {"u": event["officer_username"], "id": event["id"]},
                )
    assert officer.post("/api/audit/verify").json()["intact"] is True


def test_auth_helper_headers_work(anon):
    assert anon.get("/api/auth/me", headers=auth_headers()).json()["full_name"] == OFFICER_NAME
