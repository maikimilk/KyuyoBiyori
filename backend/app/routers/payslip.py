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
    mode: str = Form("simple"),
):
    print("DEBUG FILE SIZE", file.filename, file.content_type)
    content = await file.read()
    print("DEBUG CONTENT LENGTH", len(content))

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    if mode == "simple":
        selected_parser = parser
    elif mode == "detailed":
        from ..ocr.detailed_parser import DetailedParser
        selected_parser = DetailedParser()
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

    try:
        result = selected_parser.parse(content, mode=mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    warnings_safe = result.warnings if result.warnings is not None else []

    return PayslipPreview(
        filename=file.filename,
        gross_amount=result.gross,
        deduction_amount=result.deduction,
        net_amount=result.net,
        warnings=warnings_safe,
        items=result.items if result.items else [
            {"name": "支給合計", "amount": result.gross, "category": "支給"},
            {"name": "控除合計", "amount": result.deduction, "category": "控除"},
            {"name": "差引支給額", "amount": result.net, "category": "支給"},
        ],
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
    db.flush()

    # PayslipItem を保存する
    for item in payload.items:
        item_model = models.PayslipItem(
            payslip_id=p.id,
            name=item.name,
            amount=item.amount,
            category=item.category,
        )
        db.add(item_model)
    print("DEBUG items from payload:", payload.items)

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


@router.get("/breakdown")
def payslip_breakdown(
    year: int,
    category: str,
    db: Session = Depends(get_db),
):
    print("DEBUG /breakdown called with:", year, category)

    # カテゴリー変換マップ
    category_map = {
        "deduction": "控除",
        "payment": "支給",
    }

    # バリデーション
    if category not in category_map:
        raise HTTPException(status_code=400, detail="Invalid category")

    # DB に保存されているカテゴリ名に変換
    category_in_db = category_map[category]

    # 年の範囲
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    # payslip_id の一覧を取得
    payslip_ids = db.query(models.Payslip.id).filter(
        models.Payslip.date >= start_date,
        models.Payslip.date <= end_date
    ).all()
    payslip_ids = [pid[0] for pid in payslip_ids]

    print("DEBUG payslip_ids:", payslip_ids)
    print("DEBUG start_date:", start_date, "end_date:", end_date)

    if not payslip_ids:
        print("DEBUG No payslips found for this year.")
        return {"labels": [], "data": []}

    # PayslipItem を取得
    query = db.query(models.PayslipItem).filter(
        models.PayslipItem.payslip_id.in_(payslip_ids),
        models.PayslipItem.category == category_in_db
    )

    print("DEBUG category param:", category)
    print("DEBUG category_in_db:", category_in_db)
    print("DEBUG Query:", str(query))

    items = query.all()

    print("DEBUG total items fetched:", len(items))
    for item in items:
        print(f"DEBUG item: {item.name}, amount={item.amount}, category=[{item.category}]")

    # name ごとに金額を集計
    grouped: dict[str, int] = {}
    for item in items:
        key = item.name
        grouped[key] = grouped.get(key, 0) + item.amount

    labels = sorted(grouped.keys())
    data = [grouped[k] for k in labels]

    # すべて 0 の場合は空データとして返す
    if all(v == 0 for v in data):
        print("DEBUG All values are zero, returning empty data.")
        return {"labels": [], "data": []}

    # デバッグログ
    print("DEBUG Final labels:", labels)
    print("DEBUG Final data:", data)

    # レスポンス
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

