from datetime import datetime, date, timedelta
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
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
        gross_amount=p.gross_amount or 0,
        deduction_amount=p.deduction_amount or 0,
        net_amount=p.net_amount or 0,
    )


@router.post("/upload", response_model=PayslipPreview)
async def upload(
    file: UploadFile = File(...),
    year_month: str | None = Form(None),
):
    try:
        result = parser.parse(await file.read())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return PayslipPreview(
        filename=file.filename,
        gross_amount=result.gross,
        deduction_amount=result.deduction,
        net_amount=result.net,
        warnings=result.warnings,
        items=[],
    )


@router.post("/save", response_model=PayslipRead)
def save(payload: PayslipCreate, db: Session = Depends(get_db)):
    p = models.Payslip(
        filename=payload.filename,
        date=parse_date(payload.date),
        type=payload.type,
        gross_amount=payload.gross_amount,
        deduction_amount=payload.deduction_amount,
        net_amount=payload.net_amount,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return to_schema(p)


@router.get("/", response_model=list[PayslipRead])
def list_all(db: Session = Depends(get_db)):
    records = db.query(models.Payslip).all()
    return [to_schema(p) for p in records]


@router.get("/list", response_model=list[PayslipRead])
def list_alias(db: Session = Depends(get_db)):
    return list_all(db)


@router.get("/summary")
def payslip_summary(db: Session = Depends(get_db)):
    today = date.today()
    start_month = today.replace(day=1)
    prev_month_end = start_month - timedelta(days=1)
    start_prev_month = prev_month_end.replace(day=1)

    def sum_amount(records, attr):
        return sum(getattr(p, attr) or 0 for p in records)

    this_month = db.query(models.Payslip).filter(models.Payslip.date >= start_month).all()
    prev_month = db.query(models.Payslip).filter(
        models.Payslip.date >= start_prev_month,
        models.Payslip.date <= prev_month_end,
    ).all()
    bonus = db.query(models.Payslip).filter(models.Payslip.type == "bonus").all()

    net_this_month = sum_amount(this_month, "net_amount")
    gross_this_month = sum_amount(this_month, "gross_amount")
    deduction_this_month = sum_amount(this_month, "deduction_amount")
    net_prev_month = sum_amount(prev_month, "net_amount")
    bonus_total = sum_amount(bonus, "net_amount")

    return {
        "net_this_month": net_this_month,
        "gross_this_month": gross_this_month,
        "deduction_this_month": deduction_this_month,
        "bonus_total": bonus_total,
        "diff_vs_prev_month": net_this_month - net_prev_month,
    }


@router.get("/stats")
def payslip_stats(
    period: str = "monthly",
    target: str = "net",
    kind: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Payslip)
    if kind:
        query = query.filter(models.Payslip.type == kind)
    records = query.all()

    grouped: dict[str, int] = {}
    for p in records:
        if not p.date:
            continue
        key = p.date.strftime("%Y-%m") if period == "monthly" else p.date.strftime("%Y")
        value = 0
        if target == "net":
            value = p.net_amount or 0
        elif target == "gross":
            value = p.gross_amount or 0
        elif target == "deduction":
            value = p.deduction_amount or 0
        grouped[key] = grouped.get(key, 0) + value

    labels = sorted(grouped.keys())
    data = [grouped[k] for k in labels]
    if all(v == 0 for v in data):
        return {"labels": [], "data": []}
    return {"labels": labels, "data": data}


@router.get("/{payslip_id}", response_model=PayslipRead)
def get_one(payslip_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Payslip).get(payslip_id)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    return to_schema(p)


@router.delete("/delete")
def delete_payslip(payslip_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Payslip).get(payslip_id)
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(p)
    db.commit()
    return {"status": "deleted"}
