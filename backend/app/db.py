from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app import models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()

    from app.auth import seed_users

    db = SessionLocal()
    try:
        seed_users(db)
    finally:
        db.close()
    settings.storage_path  # ensures storage dirs exist
    for sub in ("tenders", "bids", "text", "reports"):
        (settings.storage_path / sub).mkdir(parents=True, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. `create_all` never alters existing
# tables, so add them in place on databases created by an older build.
_LATE_COLUMNS = {
    "audit_events": {
        "reason_category": "VARCHAR DEFAULT ''",
        "officer_username": "VARCHAR DEFAULT ''",
    },
    "documents": {
        "sha256": "VARCHAR DEFAULT ''",
        "source": "VARCHAR DEFAULT 'SAMPLE'",
        "file_size": "INTEGER DEFAULT 0",
        "page_texts": "JSON DEFAULT '[]'",
        "pages_without_text": "JSON DEFAULT '[]'",
        "extraction_mode": "VARCHAR DEFAULT ''",
        "extraction_note": "TEXT DEFAULT ''",
    },
    "evaluations": {
        "officer_verdict": "VARCHAR",
        "override_reason": "TEXT DEFAULT ''",
        "override_category": "VARCHAR DEFAULT ''",
        "officer_username": "VARCHAR DEFAULT ''",
        "officer_name": "VARCHAR DEFAULT ''",
        "overridden_at": "DATETIME",
    },
}


def _add_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _LATE_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
