from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy import func
from collections import defaultdict
import re
try:
    from google.cloud import vision  # type: ignore
    _vision_available = True
except Exception:  # pragma: no cover - library optional during tests
    _vision_available = False

from ..schemas import (
    PayslipCreate,
    PayslipUpdate,
    Payslip,
    PayslipPreview,
    PayslipItem,
    ReparseRequest,
)
from .. import models, database

router = APIRouter()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

_deduction_keywords = ['税', '保険', '控除', '料', '差引']


def _extract_text_with_vision(content: bytes) -> str:
    """Extract text using Google Cloud Vision API if available."""
    if not _vision_available:
        return ''

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    if response.error.message:
        raise RuntimeError(response.error.message)
    return response.full_text_annotation.text or ''


def _parse_text(text: str) -> dict:
    gross = net = deduction = None
    items: list[PayslipItem] = []
    item_pattern = re.compile(r"([\w\u3000-\u30FF\u4E00-\u9FAF]+)[:\s]+(-?\d+)")

    for line in text.splitlines():
        m = item_pattern.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        try:
            amount = int(m.group(2))
        except ValueError:
            continue

        items.append(PayslipItem(name=name, amount=amount))
        if name in ('gross', '総支給', '支給総額'):
            gross = amount
        if name in ('net', '手取り'):
            net = amount
        if name in ('deduction', '控除合計'):
            deduction = amount

    return {
        'items': items,
        'gross_amount': gross,
        'net_amount': net,
        'deduction_amount': deduction,
    }


def _categorize_items(items: list[PayslipItem]) -> list[PayslipItem]:
    categorized: list[PayslipItem] = []
    for it in items:
        category = 'payment'
        if it.amount < 0 or any(k in it.name for k in _deduction_keywords):
            category = 'deduction'
        categorized.append(PayslipItem(id=it.id, name=it.name, amount=it.amount, category=category))
    return categorized


def _parse_file(content: bytes) -> dict:
    """Parse uploaded file using OCR when necessary."""
    text = content.decode('utf-8', errors='ignore')
    parsed = _parse_text(text)
    if not parsed['items'] and _vision_available:
        try:
            vision_text = _extract_text_with_vision(content)
        except Exception:
            vision_text = ''
        parsed = _parse_text(vision_text)

    parsed['items'] = _categorize_items(parsed['items'])
    return parsed


@router.post('/upload', response_model=PayslipPreview)
async def upload_payslip(
    file: UploadFile = File(...),
):
    content = await file.read()
    parsed = _parse_file(content)
    slip_type = None
    text_blob = '\n'.join([it.name for it in parsed['items']])
    if '賞与' in text_blob or 'bonus' in text_blob.lower():
        slip_type = 'bonus'
    return PayslipPreview(
        filename=file.filename,
        date=None,
        type=slip_type,
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
    for it in data.items:
        item = models.PayslipItem(
            name=it.name,
            amount=it.amount,
            category=it.category,
            payslip_id=payslip.id,
        )
        db.add(item)
    db.commit()
    db.refresh(payslip)
    return payslip

@router.get('/', response_model=list[Payslip])
def list_payslips(db: Session = Depends(get_db)):
    return db.query(models.Payslip).all()


@router.get('/list', response_model=list[Payslip])
def list_filtered_payslips(
    year: Optional[int] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Payslip)
    if year:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        query = query.filter(models.Payslip.date >= start, models.Payslip.date <= end)
    if kind:
        query = query.filter(models.Payslip.type == kind)
    return query.all()


@router.delete('/delete')
def delete_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail='Not found')
    db.delete(payslip)
    db.commit()
    return {'status': 'deleted'}


@router.post('/reparse', response_model=list[PayslipItem])
def reparse_payslip(data: ReparseRequest):
    items = []
    for it in data.items:
        category = 'deduction' if it.amount < 0 else 'payment'
        items.append(PayslipItem(id=it.id, name=it.name, amount=it.amount, category=category))
    return items


@router.put('/update', response_model=Payslip)
def update_payslip(data: PayslipUpdate, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(data.id)
    if not payslip:
        raise HTTPException(status_code=404, detail='Not found')
    payslip.filename = data.filename
    payslip.date = datetime.strptime(data.date, "%Y-%m-%d").date() if data.date else None
    payslip.type = data.type
    payslip.gross_amount = data.gross_amount
    payslip.net_amount = data.net_amount
    payslip.deduction_amount = data.deduction_amount
    payslip.items.clear()
    for it in data.items:
        payslip.items.append(models.PayslipItem(name=it.name, amount=it.amount, category=it.category))
    db.commit()
    db.refresh(payslip)
    return payslip

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
def payslip_stats(period: str = 'monthly', target: str = 'net', kind: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Payslip)
    if kind:
        query = query.filter(models.Payslip.type == kind)
    records = query.all()
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

@router.get('/export')
def export_payslips(format: str = 'csv', db: Session = Depends(get_db)):
    payslips = db.query(models.Payslip).all()
    records = [
        {
            'id': p.id,
            'date': p.date.isoformat() if p.date else '',
            'type': p.type,
            'gross_amount': p.gross_amount,
            'net_amount': p.net_amount,
            'deduction_amount': p.deduction_amount,
        }
        for p in payslips
    ]
    if format == 'json':
        return records
    header = ['id','date','type','gross_amount','net_amount','deduction_amount']
    def iter_csv():
        yield ','.join(header) + '\n'
        for r in records:
            row = [str(r[h]) if r[h] is not None else '' for h in header]
            yield ','.join(row) + '\n'
    return StreamingResponse(iter_csv(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=payslips.csv'})

@router.get('/breakdown')
def payslip_breakdown(year: int | None = None, category: str = 'deduction', db: Session = Depends(get_db)):
    query = db.query(models.PayslipItem.name, func.sum(models.PayslipItem.amount)).join(models.Payslip)
    if year:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        query = query.filter(models.Payslip.date >= start, models.Payslip.date <= end)
    if category:
        query = query.filter(models.PayslipItem.category == category)
    query = query.group_by(models.PayslipItem.name)
    results = query.all()
    labels = [r[0] for r in results]
    data = [r[1] for r in results]
    return { 'labels': labels, 'data': data }

@router.get('/{payslip_id}', response_model=Payslip)
def get_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail='Not found')
    return payslip
