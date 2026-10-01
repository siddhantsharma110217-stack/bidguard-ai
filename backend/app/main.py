from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, bids, demo, evaluations, redflags, tenders, uploads
from app.api.uploads import MAX_FILES
from app.config import settings
from app.db import init_db
from app.extraction.service import MODE_LABELS, active_mode


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="BidGuard AI", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Refuse oversized uploads before the multipart body is read and spooled.

    The per-file limit is enforced again (with a friendlier, per-file message)
    in the upload endpoint; this only caps the whole request.
    """
    if request.url.path.endswith("/bids/upload"):
        cap = (settings.max_upload_mb * MAX_FILES + 1) * 1024 * 1024
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > cap:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"The upload is too large. Each file may be at most "
                        f"{settings.max_upload_mb} MB, and at most {MAX_FILES} files."
                    )
                },
            )
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ai_provider": settings.ai_provider,
        "database_url": settings.database_url,
        # Only the mode is exposed; the API key never leaves the backend.
        "extraction_mode": active_mode(),
        "extraction_label": MODE_LABELS[active_mode()],
        "extraction_model": settings.extraction_model if active_mode() == "AI" else "",
        "max_upload_mb": settings.max_upload_mb,
    }


app.include_router(tenders.router)
app.include_router(bids.router)
app.include_router(evaluations.router)
app.include_router(demo.router)
app.include_router(audit.router)
app.include_router(redflags.router)
app.include_router(uploads.router)
