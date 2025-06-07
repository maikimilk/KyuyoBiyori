from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from collections import defaultdict
from ..schemas import PayslipCreate, Payslip, PayslipPreview, PayslipItem
from .. import models, database

router = APIRouter()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _parse_file(content: bytes) -> dict:
    """Very naive parser used as a stub for OCR."""
    text = content.decode('utf-8', errors='ignore')
    gross = net = deduction = None
    items: list[PayslipItem] = []
    for line in text.splitlines():
        if ':' in line:
            name, value = line.split(':', 1)
            try:
                amount = int(value.strip())
            except ValueError:
                continue
            items.append(PayslipItem(name=name.strip(), amount=amount))
            if name.strip() == 'gross':
                gross = amount
            if name.strip() == 'net':
                net = amount
            if name.strip() == 'deduction':
                deduction = amount
    return {
        'items': items,
        'gross_amount': gross,
        'net_amount': net,
        'deduction_amount': deduction,
    }


@router.post('/upload', response_model=PayslipPreview)
async def upload_payslip(
    file: UploadFile = File(...),
):
    content = await file.read()
    parsed = _parse_file(content)
    return PayslipPreview(
        filename=file.filename,
        date=None,
        type=None,
        gross_amount=parsed.get('gross_amount'),
        net_amount=parsed.get('net_amount'),
        deduction_amount=parsed.get('deduction_amount'),
        items=parsed['items'],
    )


@router.post('/save', response_model=Payslip)
def save_payslip(
    data: PayslipCreate,
    db: Session = Depends(get_db)
):
    date_obj = datetime.strptime(data.date, "%Y-%m-%d").date() if data.date else None
    payslip = models.Payslip(
        filename=data.filename,
        date=date_obj,
        type=data.type,
        gross_amount=data.gross_amount,
        net_amount=data.net_amount,
        deduction_amount=data.deduction_amount,
    )
    db.add(payslip)
    db.commit()
    db.refresh(payslip)
    return payslip

@router.get('/', response_model=list[Payslip])
def list_payslips(db: Session = Depends(get_db)):
    return db.query(models.Payslip).all()

@router.get('/summary')
def payslip_summary(db: Session = Depends(get_db)):
    today = date.today()
    start_month = today.replace(day=1)
    prev_month_end = start_month - timedelta(days=1)
    start_prev_month = prev_month_end.replace(day=1)

    def sum_amount(query):
        return sum(x or 0 for x in query)

    this_month = db.query(models.Payslip).filter(models.Payslip.date >= start_month)
    prev_month = db.query(models.Payslip).filter(models.Payslip.date >= start_prev_month, models.Payslip.date <= prev_month_end)
    bonus = db.query(models.Payslip).filter(models.Payslip.type == 'bonus')

    net_this_month = sum_amount([p.net_amount for p in this_month])
    gross_this_month = sum_amount([p.gross_amount for p in this_month])
    net_prev_month = sum_amount([p.net_amount for p in prev_month])
    bonus_total = sum_amount([p.net_amount for p in bonus])

    return {
        'net_this_month': net_this_month,
        'gross_this_month': gross_this_month,
        'bonus_total': bonus_total,
        'diff_vs_prev_month': net_this_month - net_prev_month,
    }

@router.get('/stats')
def payslip_stats(period: str = 'monthly', target: str = 'net', db: Session = Depends(get_db)):
    records = db.query(models.Payslip).all()
    grouped = defaultdict(int)
    for p in records:
        if not p.date:
            continue
        if period == 'monthly':
            key = p.date.strftime('%Y-%m')
        else:
            key = p.date.strftime('%Y')
        value = 0
        if target == 'net':
            value = p.net_amount or 0
        elif target == 'gross':
            value = p.gross_amount or 0
        elif target == 'deduction':
            value = p.deduction_amount or 0
        grouped[key] += value

    labels = sorted(grouped.keys())
    data = [grouped[k] for k in labels]
    return {'labels': labels, 'data': data}

@router.get('/{payslip_id}', response_model=Payslip)
def get_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail='Not found')
    return payslip
