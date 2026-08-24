"""Phase 1 sanity checks: app boots, DB initializes, config loads."""

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Tender


def test_health_ok():
    init_db()
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["ai_provider"] == "mock"


def test_db_initializes_and_is_writable():
    init_db()
    db = SessionLocal()
    try:
        tender = Tender(title="Sanity Check Tender", reference_no="TEST-0001")
        db.add(tender)
        db.commit()
        db.refresh(tender)
        assert tender.id is not None
        assert tender.status == "UPLOADED"
    finally:
        db.query(Tender).filter(Tender.reference_no == "TEST-0001").delete()
        db.commit()
        db.close()


def test_mock_provider_raises_clear_error_when_fixture_missing():
    from app.ai.mock_provider import FixtureNotFound, MockProvider

    provider = MockProvider()
    try:
        provider.complete_json(task="nonexistent_task", prompt="x", schema={})
        assert False, "expected FixtureNotFound"
    except FixtureNotFound as e:
        assert "nonexistent_task" in str(e)
