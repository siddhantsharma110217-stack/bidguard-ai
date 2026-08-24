from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Requirement, Tender
from app.schemas import RequirementListOut, RequirementOut, TenderOut

router = APIRouter(prefix="/api/tenders", tags=["tenders"])


def _requirement_out(req: Requirement) -> RequirementOut:
    return RequirementOut(
        id=req.id,
        code=req.code,
        category=req.category,
        title=req.title,
        description=req.description,
        obligation=req.obligation,
        rule_type=req.rule_type,
        weight=req.weight,
        source_page=req.source_page,
        source_clause=req.source_clause,
        expected_condition=(req.rule_params or {}).get("expected_display", ""),
    )


def get_tender_or_404(tender_id: int, db: Session) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} was not found.")
    return tender


@router.get("", response_model=list[TenderOut])
def list_tenders(db: Session = Depends(get_db)):
    return db.query(Tender).order_by(Tender.id).all()


@router.post("", response_model=TenderOut, status_code=201)
def create_tender(payload: dict, db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="A tender title is required.")

    tender = Tender(
        title=title,
        reference_no=payload.get("reference_no", ""),
        filename=payload.get("filename", ""),
        status="READY",
        meta=payload.get("meta", {}),
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)
    return tender


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: int, db: Session = Depends(get_db)):
    return get_tender_or_404(tender_id, db)


@router.get("/{tender_id}/requirements", response_model=RequirementListOut)
def get_requirements(tender_id: int, db: Session = Depends(get_db)):
    tender = get_tender_or_404(tender_id, db)
    reqs = (
        db.query(Requirement)
        .filter(Requirement.tender_id == tender_id)
        .order_by(Requirement.code)
        .all()
    )
    return RequirementListOut(
        tender=TenderOut.model_validate(tender),
        total=len(reqs),
        mandatory=sum(1 for r in reqs if r.obligation == "MANDATORY"),
        desirable=sum(1 for r in reqs if r.obligation == "DESIRABLE"),
        requirements=[_requirement_out(r) for r in reqs],
    )
