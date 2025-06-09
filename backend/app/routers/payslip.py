from datetime import datetime, date
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import database, models
from ..ocr.simple_totals import TotalsOnlyParser
from ..ocr.strategy import BaseParser
from ..schemas.payslip import PayslipCreate, PayslipPreview, PayslipRead

router = APIRouter()
parser: BaseParser = TotalsOnlyParser()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == "%Y-%m":
                dt = dt.replace(day=1)
            return dt.date()
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="Invalid date format")


def to_schema(p: models.Payslip) -> PayslipRead:
    return PayslipRead(
        id=p.id,
        filename=p.filename,
        date=p.date.isoformat() if p.date else None,
        type=p.type,
        gross=p.gross_amount or 0,
        deduction=p.deduction_amount or 0,
        net=p.net_amount or 0,
    )


@router.post("/upload", response_model=PayslipPreview)
async def upload(file: UploadFile = File(...)):
    result = parser.parse(await file.read())
    return PayslipPreview(
        filename=file.filename,
        gross=result.gross,
        deduction=result.deduction,
        net=result.net,
        warnings=result.warnings,
    )


@router.post("/save", response_model=PayslipRead)
def save(payload: PayslipCreate, db: Session = Depends(get_db)):
    p = models.Payslip(
        filename=payload.filename,
        date=parse_date(payload.date),
        type=payload.type,
        gross_amount=payload.gross,
        deduction_amount=payload.deduction,
        net_amount=payload.net,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return to_schema(p)


@router.get("/", response_model=list[PayslipRead])
def list_all(db: Session = Depends(get_db)):
    records = db.query(models.Payslip).all()
    return [to_schema(p) for p in records]
