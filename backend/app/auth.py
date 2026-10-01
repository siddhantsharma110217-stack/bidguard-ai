"""Prototype officer login: seeded demo users, salted password hashes and
HMAC-signed session tokens. Deliberately small; there is no user management.

* Users are seeded from configuration (`DEMO_USERS` + passwords read from
  environment variables, with clearly labelled demo defaults). Only salted
  scrypt hashes are stored.
* A token is `base64url(payload).base64url(HMAC-SHA256(payload))`, where the
  payload holds the username and an expiry. Tokens are stateless: logging
  out discards the token in the browser; it stays valid until it expires.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

OFFICER = "OFFICER"
REVIEWER = "REVIEWER"


@dataclass(frozen=True)
class SeedUser:
    username: str
    full_name: str
    designation: str
    role: str
    password_setting: str  # Settings attribute (env var) holding the password


# DEMO ACCOUNTS (fictional people). Passwords come from the environment:
# DEMO_OFFICER1_PASSWORD, DEMO_OFFICER2_PASSWORD, DEMO_REVIEWER_PASSWORD.
DEMO_USERS = [
    SeedUser("asharma", "Anita Sharma", "Evaluation Officer", OFFICER, "demo_officer1_password"),
    SeedUser("riyer", "Rahul Iyer", "Assistant Evaluation Officer", OFFICER, "demo_officer2_password"),
    SeedUser("kmenon", "Kavita Menon", "Audit Reviewer", REVIEWER, "demo_reviewer_password"),
]

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(digest_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def seed_password(user: SeedUser) -> str:
    return getattr(settings, user.password_setting)


def password_is_demo_default(user: SeedUser) -> bool:
    default = type(settings).model_fields[user.password_setting].default
    return seed_password(user) == default


def seed_users(db: Session) -> None:
    """Create the demo users, or re-hash a password changed in the environment."""
    for spec in DEMO_USERS:
        password = seed_password(spec)
        user = db.get(User, spec.username)
        if user is None:
            db.add(
                User(
                    username=spec.username,
                    full_name=spec.full_name,
                    designation=spec.designation,
                    role=spec.role,
                    password_hash=hash_password(password),
                )
            )
        else:
            user.full_name, user.designation, user.role = spec.full_name, spec.designation, spec.role
            if not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)
    db.commit()


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(settings.session_secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())


def create_token(username: str, ttl_seconds: int | None = None, now: float | None = None) -> tuple[str, int]:
    """Return (token, expiry as a Unix timestamp)."""
    ttl = settings.session_ttl_minutes * 60 if ttl_seconds is None else ttl_seconds
    exp = int((now or time.time()) + ttl)
    payload = _b64(json.dumps({"sub": username, "exp": exp}, separators=(",", ":")).encode("utf-8"))
    return f"{payload}.{_sign(payload)}", exp


class InvalidToken(Exception):
    pass


def read_token(token: str) -> str:
    """The username in a valid token. Raises InvalidToken otherwise."""
    try:
        payload, signature = token.split(".")
    except ValueError as exc:
        raise InvalidToken("malformed token") from exc
    if not hmac.compare_digest(signature, _sign(payload)):
        raise InvalidToken("bad signature")
    try:
        data = json.loads(_unb64(payload))
        username, exp = data["sub"], int(data["exp"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidToken("malformed payload") from exc
    if exp <= time.time():
        raise InvalidToken("expired")
    return username


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def current_user(
    authorization: str = Header(default=""), db: Session = Depends(get_db)
) -> User:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    try:
        username = read_token(token.strip())
    except InvalidToken as exc:
        detail = (
            "Your session has expired. Please log in again."
            if str(exc) == "expired"
            else "Your session is not valid. Please log in again."
        )
        raise HTTPException(status_code=401, detail=detail) from exc
    user = db.get(User, username)
    if user is None:
        raise HTTPException(status_code=401, detail="Your session is not valid. Please log in again.")
    return user


def require_officer(user: User = Depends(current_user)) -> User:
    if user.role != OFFICER:
        raise HTTPException(
            status_code=403,
            detail=(
                f"{user.full_name} is logged in as {user.role}. Only an evaluation "
                "officer can do this; reviewers have read-only access."
            ),
        )
    return user
