from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import audit, bids, demo, evaluations, redflags, tenders
from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="BidGuard AI", version="0.2.0", lifespan=lifespan)

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
    }


app.include_router(tenders.router)
app.include_router(bids.router)
app.include_router(evaluations.router)
app.include_router(demo.router)
app.include_router(audit.router)
app.include_router(redflags.router)
