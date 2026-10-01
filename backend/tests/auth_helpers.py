"""Authenticate test clients without going through the login form.

Existing tests just swap `TestClient(app)` for `officer_client()`; tokens
are minted directly (the users exist because init_db seeds them).
"""

from fastapi.testclient import TestClient

from app.auth import DEMO_USERS, create_token
from app.main import app

OFFICER = next(u for u in DEMO_USERS if u.username == "asharma")
SECOND_OFFICER = next(u for u in DEMO_USERS if u.username == "riyer")
REVIEWER = next(u for u in DEMO_USERS if u.role == "REVIEWER")

OFFICER_USERNAME = OFFICER.username
OFFICER_NAME = OFFICER.full_name  # what every override made by officer_client() records


def auth_headers(username: str = OFFICER_USERNAME) -> dict[str, str]:
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


def client_as(username: str) -> TestClient:
    client = TestClient(app)
    client.headers.update(auth_headers(username))
    return client


def officer_client() -> TestClient:
    return client_as(OFFICER_USERNAME)


def reviewer_client() -> TestClient:
    return client_as(REVIEWER.username)
