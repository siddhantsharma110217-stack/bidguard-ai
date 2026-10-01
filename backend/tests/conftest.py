"""Test isolation.

Point the app at a dedicated test database BEFORE `app.config` /`app.db` are
imported, so tests never read or mutate the development `bidguard.db`.
Environment variables take precedence over `.env` in pydantic-settings.
"""

import os
import pathlib
import shutil
import tempfile

_TEST_DB = pathlib.Path(__file__).resolve().parent / "bidguard_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
# Never make real API calls from tests, even if a developer's .env has a key:
# AI extraction is exercised only through fake providers.
os.environ["ANTHROPIC_API_KEY"] = ""
# Uploaded files go to a throwaway folder, not backend/storage.
_TEST_STORAGE = tempfile.mkdtemp(prefix="bidguard-test-storage-")
os.environ["STORAGE_DIR"] = _TEST_STORAGE

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
    shutil.rmtree(_TEST_STORAGE, ignore_errors=True)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
