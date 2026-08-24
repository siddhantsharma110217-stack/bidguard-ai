"""Test isolation.

Point the app at a dedicated test database BEFORE `app.config` /`app.db` are
imported, so tests never read or mutate the development `bidguard.db`.
Environment variables take precedence over `.env` in pydantic-settings.
"""

import os
import pathlib

_TEST_DB = pathlib.Path(__file__).resolve().parent / "bidguard_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _fresh_database():
    """Start every test session from an empty schema."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
