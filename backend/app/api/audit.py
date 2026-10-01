from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import verify_chain
from app.db import get_db
from app.models import AuditEvent
from app.schemas import AuditEventOut, AuditVerifyOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
def list_events(db: Session = Depends(get_db)):
    return db.query(AuditEvent).order_by(AuditEvent.id).all()


@router.post("/verify", response_model=AuditVerifyOut)
def verify(db: Session = Depends(get_db)):
    """Recompute the whole hash chain and report the first broken event."""
    return verify_chain(db)
