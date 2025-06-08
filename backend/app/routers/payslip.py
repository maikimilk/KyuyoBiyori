from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy import func
from collections import defaultdict
import logging
import re

logger = logging.getLogger(__name__)
# Ensure INFO level logs are emitted even when root logger level is higher
if not logger.handlers:
    logger.setLevel(logging.INFO)
try:
    from google.cloud import vision  # type: ignore

    _vision_available = True
    logger.info("Google Cloud Vision API client loaded")
except Exception as e:  # pragma: no cover - library optional during tests
    _vision_available = False
    logger.warning("Google Cloud Vision API not available: %s", e)

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


_deduction_keywords = ["税", "保険", "控除", "料", "差引"]

# units that indicate quantities rather than monetary amounts
# "月" は給与明細のタイトルに自然に含まれるため除外する
QUANTITY_UNITS = ["日", "人", "時間", "回", "回数", "週"]
# pattern to detect attendance items such as "欠勤日数" or "残業時間"
ATTENDANCE_PATTERN = re.compile(r"(日数|時間|回数?|人|週)$")

GROSS_KEYS = ("gross", "総支給", "支給総額", "支給合計", "総支給額")
NET_KEYS = ("net", "手取り", "差引支給額")
DEDUCTION_KEYS = ("deduction", "控除合計")
TOTAL_KEYS = set(GROSS_KEYS) | set(NET_KEYS) | set(DEDUCTION_KEYS)

# known item names for explicit categorization
CATEGORY_MAP = {
    "健康保険料": "deduction",
    "厚生年金保険": "deduction",
    "雇用保険料": "deduction",
    "所得税": "deduction",
    "本給": "payment",
    "支給額": "payment",
    "通勤費補助": "payment",
    "東友会費": "deduction",
    "共済会費": "deduction",
    "社員会費": "deduction",
    "控除合計": "deduction",
    "差引支給額": "net",
    "雇保対象額": "skip",
    "当月所得税累計": "skip",
    "口座振込額": "net",
}

# common section headers that should not be treated as item names
KNOWN_SECTION_LABELS = [
    # 明細で確認されているもの
    "支給項目",
    "控除項目",
    "就業項目",
    "当月欄",
    "年間累計欄",
    # 一般汎用
    "基本情報",
    "社員情報",
    "勤怠情報",
    "勤務情報",
    "個人情報",
    "所属情報",
    "支給内訳",
    "控除内訳",
    "勤怠明細",
    "勤怠項目",
    "当月明細",
    "年間累計",
    "差引支給額欄",
    "賞与明細",
    "賞与欄",
    "手当項目",
    "保険料明細",
    "その他",
    "備考欄",
    "支給合計欄",
    "控除合計欄",
    # 特殊系
    "課税対象額",
    "社会保険対象額",
    "雇保対象額",
    "退職金対象額",
    "年末調整対象額",
]

# mapping of known section headers to internal section names
SECTION_MAP = {
    "支給項目": "payment",
    "控除項目": "deduction",
    "就業項目": "attendance",
    "勤怠項目": "attendance",
    "勤怠明細": "attendance",
    "勤怠情報": "attendance",
    "勤務情報": "attendance",
    "当月欄": "当月",
    "年間累計欄": "年間累計",
}

# labels that contain employee metadata and should never become payslip items
KNOWN_METADATA_LABELS = [
    "社員番号",
    "氏名",
    "資格",
    "所属",
    "役職",
    "事業所名",
    "部門名",
    "部署",
    "支店名",
    "住所",
    "電話番号",
]


def _detect_slip_type(text: str) -> str | None:
    """Heuristically detect payslip type from OCR text."""
    if not text:
        return None

    lines = text.splitlines()
    header = lines[0][:20] if lines else ""

    slip_type = None
    if "賞与支給明細書" in header:
        slip_type = "bonus"
    elif "給与支給明細書" in header:
        slip_type = "salary"
    elif re.search(r"^\s*賞与[額支給]?", header):
        slip_type = "bonus"
    elif re.search(r"^\s*給与[額支給]?", header):
        slip_type = "salary"

    if slip_type is None:
        if "賞与" in text or "bonus" in text.lower():
            slip_type = "bonus"
        elif "給与" in text or "salary" in text.lower():
            slip_type = "salary"
    return slip_type


def _extract_text_with_vision(content: bytes) -> str:
    """Extract text using Google Cloud Vision API if available."""
    if not _vision_available:
        logger.debug("Vision API not available; skipping OCR")
        return ""

    logger.info("Sending image to Google Cloud Vision API")
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    if response.error.message:
        logger.error("Vision API error: %s", response.error.message)
        raise RuntimeError(response.error.message)
    text = response.full_text_annotation.text or ""
    logger.info("Vision API returned %d characters", len(text))
    logger.info("Vision API OCR result:\n%s", text)
    return text


def _parse_text(text: str) -> dict:
    gross = net = deduction = None
    items: list[PayslipItem] = []
    attendance: dict[str, int] = {}

    # line patterns
    item_amount = re.compile(r"^([^\d]+?)[：:\s]+([\-−△▲]?\d[\d,]*)$")
    item_attendance = re.compile(r"^([^\d]+?)[：:\s]+(\d+)(日|人|時間|回数?|週)$")
    amount_only = re.compile(r"^[\-−△▲]?\d[\d,]*$")
    value_with_unit = re.compile(r"^(\d+)(日|人|時間|回数?|週)$")
    amount_first_pattern = re.compile(r"^([\-−△▲]?\d[\d,]*)\s+(.+)$")

    def _clean_amount(s: str) -> int:
        return int(
            re.sub(rf"({'|'.join(QUANTITY_UNITS)})$", "", s)
            .replace(",", "")
            .replace("−", "-")
            .replace("△", "-")
            .replace("▲", "-")
        )

    current_section = None
    pending_names: list[str] = []
    reset_sections = ("支給合計", "控除合計", "差引支給額")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line in reset_sections:
            current_section = None
            pending_names.clear()
            continue

        if line in SECTION_MAP:
            current_section = SECTION_MAP[line]
            pending_names.clear()
            continue

        if line in KNOWN_SECTION_LABELS:
            cleaned = re.sub(r"\d+$", "", line.strip())
            if cleaned:
                pending_names.append(cleaned)
            else:
                pending_names.clear()
            continue

        if any(line.startswith(lbl) for lbl in KNOWN_METADATA_LABELS):
            pending_names.clear()
            continue

        m_att = item_attendance.match(line)
        if m_att:
            name, value, _u = m_att.groups()
            attendance[name.strip()] = int(value)
            pending_names.clear()
            continue

        m = item_amount.match(line)
        if m:
            name, value = m.groups()
            name = re.sub(r"\d+$", "", name.strip())
            if not name or name in KNOWN_METADATA_LABELS:
                pending_names.clear()
                continue
            try:
                amount = _clean_amount(value)
            except ValueError:
                pending_names.clear()
                continue
            section = current_section
            if section == "attendance" or ATTENDANCE_PATTERN.search(name) or name in QUANTITY_UNITS:
                attendance[name] = amount
            elif name in TOTAL_KEYS:
                if name in GROSS_KEYS:
                    gross = amount
                if name in NET_KEYS:
                    net = amount
                if name in DEDUCTION_KEYS:
                    deduction = amount
            else:
                if section != "attendance" and abs(amount) < 10:
                    logger.warning(
                        "Skipping suspicious small amount %s for %s", amount, name
                    )
                else:
                    items.append(PayslipItem(name=name, amount=amount, section=section))
            pending_names.clear()
            continue

        if value_with_unit.match(line) and pending_names:
            v, _u = value_with_unit.match(line).groups()
            name = pending_names.pop(0)
            attendance[name] = int(v)
            continue

        if amount_only.match(line):
            if pending_names:
                name = pending_names.pop(0)
                try:
                    amount = _clean_amount(line)
                except ValueError:
                    continue
                section = current_section
                if section == "attendance" or ATTENDANCE_PATTERN.search(name) or name in QUANTITY_UNITS:
                    attendance[name] = amount
                elif name in TOTAL_KEYS:
                    if name in GROSS_KEYS:
                        gross = amount
                    if name in NET_KEYS:
                        net = amount
                    if name in DEDUCTION_KEYS:
                        deduction = amount
                else:
                    if section != "attendance" and abs(amount) < 10:
                        logger.warning(
                            "Skipping suspicious small amount %s for %s", amount, name
                        )
                    else:
                        items.append(PayslipItem(name=name, amount=amount, section=section))
            else:
                try:
                    amount = _clean_amount(line)
                except ValueError:
                    continue
                if abs(amount) < 10:
                    continue
                logger.warning("Amount without item name: %s", line)
            continue

        m_first = amount_first_pattern.match(line)
        if m_first:
            try:
                amount = _clean_amount(m_first.group(1))
            except ValueError:
                pending_names.clear()
                continue
            name = re.sub(r"\d+$", "", m_first.group(2).strip())
            if pending_names:
                prev_name = pending_names.pop(0)
                section_prev = current_section
                if section_prev == "attendance" or ATTENDANCE_PATTERN.search(prev_name) or prev_name in QUANTITY_UNITS:
                    attendance[prev_name] = amount
                elif prev_name in TOTAL_KEYS:
                    if prev_name in GROSS_KEYS:
                        gross = amount
                    if prev_name in NET_KEYS:
                        net = amount
                    if prev_name in DEDUCTION_KEYS:
                        deduction = amount
                else:
                    if section_prev != "attendance" and abs(amount) < 10:
                        logger.warning(
                            "Skipping suspicious small amount %s for %s", amount, prev_name
                        )
                    else:
                        items.append(PayslipItem(name=prev_name, amount=amount, section=section_prev))
                if name and name not in KNOWN_METADATA_LABELS:
                    pending_names.append(name)
                continue

            if not name or name in KNOWN_METADATA_LABELS:
                pending_names.clear()
                continue
            section = current_section
            if section == "attendance" or ATTENDANCE_PATTERN.search(name) or name in QUANTITY_UNITS:
                attendance[name] = amount
            elif name in TOTAL_KEYS:
                if name in GROSS_KEYS:
                    gross = amount
                if name in NET_KEYS:
                    net = amount
                if name in DEDUCTION_KEYS:
                    deduction = amount
            else:
                if section != "attendance" and abs(amount) < 10 and not pending_names:
                    logger.warning(
                        "Skipping suspicious small amount %s for %s", amount, name
                    )
                else:
                    items.append(PayslipItem(name=name, amount=amount, section=section))
            continue

        if re.match(r"^[^\d]+$", line):
            cleaned = re.sub(r"\d+$", "", line.strip())
            if cleaned and cleaned not in KNOWN_METADATA_LABELS and cleaned not in KNOWN_SECTION_LABELS:
                pending_names.append(cleaned)
            continue

        # Token-based fallback for lines containing multiple pairs
        tokens = re.split(r"\s+", line)
        handled = False
        for token in tokens:
            if not token:
                continue
            m_val = value_with_unit.match(token)
            if m_val and pending_names:
                v, _u = m_val.groups()
                name = pending_names.pop(0)
                attendance[name] = int(v)
                handled = True
                continue
            if amount_only.match(token):
                if pending_names:
                    name = pending_names.pop(0)
                    try:
                        amount = _clean_amount(token)
                    except ValueError:
                        continue
                    section = current_section
                    if section == "attendance" or ATTENDANCE_PATTERN.search(name) or name in QUANTITY_UNITS:
                        attendance[name] = amount
                    elif name in TOTAL_KEYS:
                        if name in GROSS_KEYS:
                            gross = amount
                        if name in NET_KEYS:
                            net = amount
                        if name in DEDUCTION_KEYS:
                            deduction = amount
                    else:
                        if section != "attendance" and abs(amount) < 10:
                            logger.warning(
                                "Skipping suspicious small amount %s for %s", amount, name
                            )
                        else:
                            items.append(PayslipItem(name=name, amount=amount, section=section))
                else:
                    try:
                        amount = _clean_amount(token)
                    except ValueError:
                        continue
                    if abs(amount) < 10:
                        continue
                    logger.warning("Amount without item name: %s", token)
                handled = True
                continue

            if re.match(r"^[^\d]+$", token):
                cleaned = re.sub(r"\d+$", "", token)
                if cleaned and cleaned not in KNOWN_METADATA_LABELS and cleaned not in KNOWN_SECTION_LABELS:
                    pending_names.append(cleaned)
                handled = True
                continue

            # token that mixes digits and text, treat as name with trailing digits removed
            if re.search(r"\d", token):
                cleaned = re.sub(r"\d+$", "", token)
                if cleaned and cleaned not in KNOWN_METADATA_LABELS and cleaned not in KNOWN_SECTION_LABELS:
                    pending_names.append(cleaned)
                handled = True

        if handled:
            continue

        pending_names.clear()

    return {
        "items": items,
        "gross_amount": gross,
        "net_amount": net,
        "deduction_amount": deduction,
        "attendance": attendance,
    }


def _categorize_items(items: list[PayslipItem]) -> list[PayslipItem]:
    categorized: list[PayslipItem] = []
    for it in items:
        category = it.category or CATEGORY_MAP.get(it.name)
        if not category:
            if it.section == "attendance" or ATTENDANCE_PATTERN.search(it.name):
                category = "attendance"
            elif it.amount < 0 or any(k in it.name for k in _deduction_keywords):
                category = "deduction"
            else:
                category = "payment"
            if it.name not in CATEGORY_MAP:
                logger.info(
                    "Unknown item name encountered: %s -> %s", it.name, category
                )
        if category == "skip":
            continue
        categorized.append(
            PayslipItem(
                id=it.id,
                name=it.name,
                amount=it.amount,
                category=category,
                section=it.section,
            )
        )
    return categorized


def _parse_file(content: bytes) -> dict:
    """Parse uploaded file using OCR when possible."""
    logger.debug("Parsing uploaded file")

    vision_text = ""
    if _vision_available:
        try:
            vision_text = _extract_text_with_vision(content)
        except Exception as e:
            logger.error("Vision API request failed: %s", e)
    else:
        logger.warning("Vision API client not loaded; skipping OCR")

    text = vision_text or content.decode("utf-8", errors="ignore")
    parsed = _parse_text(text)

    parsed["items"] = _categorize_items(parsed["items"])
    parsed["text"] = text
    return parsed


def _parse_date(date_str: str | None) -> date | None:
    """Parse date string which may be YYYY-MM or YYYY-MM-DD."""
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


@router.post("/upload", response_model=PayslipPreview)
async def upload_payslip(
    file: UploadFile = File(...),
):
    content = await file.read()
    parsed = _parse_file(content)
    slip_type = _detect_slip_type(parsed.get("text", ""))
    return PayslipPreview(
        filename=file.filename,
        date=None,
        type=slip_type,
        gross_amount=parsed.get("gross_amount"),
        net_amount=parsed.get("net_amount"),
        deduction_amount=parsed.get("deduction_amount"),
        items=parsed["items"],
    )


@router.post("/save", response_model=Payslip)
def save_payslip(data: PayslipCreate, db: Session = Depends(get_db)):
    date_obj = _parse_date(data.date)
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


@router.get("/", response_model=list[Payslip])
def list_payslips(db: Session = Depends(get_db)):
    return db.query(models.Payslip).all()


@router.get("/list", response_model=list[Payslip])
def list_filtered_payslips(
    year: Optional[int] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Payslip)
    if year:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        query = query.filter(models.Payslip.date >= start, models.Payslip.date <= end)
    if kind:
        query = query.filter(models.Payslip.type == kind)
    return query.all()


@router.delete("/delete")
def delete_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(payslip)
    db.commit()
    return {"status": "deleted"}


@router.post("/reparse", response_model=list[PayslipItem])
def reparse_payslip(data: ReparseRequest):
    items = []
    for it in data.items:
        category = "deduction" if it.amount < 0 else "payment"
        items.append(
            PayslipItem(
                id=it.id,
                name=it.name,
                amount=it.amount,
                category=category,
                section=it.section,
            )
        )
    return items


@router.put("/update", response_model=Payslip)
def update_payslip(data: PayslipUpdate, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(data.id)
    if not payslip:
        raise HTTPException(status_code=404, detail="Not found")
    payslip.filename = data.filename
    payslip.date = _parse_date(data.date)
    payslip.type = data.type
    payslip.gross_amount = data.gross_amount
    payslip.net_amount = data.net_amount
    payslip.deduction_amount = data.deduction_amount
    payslip.items.clear()
    for it in data.items:
        payslip.items.append(
            models.PayslipItem(name=it.name, amount=it.amount, category=it.category)
        )
    db.commit()
    db.refresh(payslip)
    return payslip


@router.get("/summary")
def payslip_summary(db: Session = Depends(get_db)):
    today = date.today()
    start_month = today.replace(day=1)
    prev_month_end = start_month - timedelta(days=1)
    start_prev_month = prev_month_end.replace(day=1)

    def sum_amount(query):
        return sum(x or 0 for x in query)

    this_month = db.query(models.Payslip).filter(models.Payslip.date >= start_month)
    prev_month = db.query(models.Payslip).filter(
        models.Payslip.date >= start_prev_month, models.Payslip.date <= prev_month_end
    )
    bonus = db.query(models.Payslip).filter(models.Payslip.type == "bonus")

    net_this_month = sum_amount([p.net_amount for p in this_month])
    gross_this_month = sum_amount([p.gross_amount for p in this_month])
    net_prev_month = sum_amount([p.net_amount for p in prev_month])
    bonus_total = sum_amount([p.net_amount for p in bonus])

    return {
        "net_this_month": net_this_month,
        "gross_this_month": gross_this_month,
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
    grouped = defaultdict(int)
    for p in records:
        if not p.date:
            continue
        if period == "monthly":
            key = p.date.strftime("%Y-%m")
        else:
            key = p.date.strftime("%Y")
        value = 0
        if target == "net":
            value = p.net_amount or 0
        elif target == "gross":
            value = p.gross_amount or 0
        elif target == "deduction":
            value = p.deduction_amount or 0
        grouped[key] += value

    labels = sorted(grouped.keys())
    data = [grouped[k] for k in labels]
    return {"labels": labels, "data": data}


@router.get("/export")
def export_payslips(format: str = "csv", db: Session = Depends(get_db)):
    payslips = db.query(models.Payslip).all()
    records = [
        {
            "id": p.id,
            "date": p.date.isoformat() if p.date else "",
            "type": p.type,
            "gross_amount": p.gross_amount,
            "net_amount": p.net_amount,
            "deduction_amount": p.deduction_amount,
        }
        for p in payslips
    ]
    if format == "json":
        return records
    header = ["id", "date", "type", "gross_amount", "net_amount", "deduction_amount"]

    def iter_csv():
        yield ",".join(header) + "\n"
        for r in records:
            row = [str(r[h]) if r[h] is not None else "" for h in header]
            yield ",".join(row) + "\n"

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payslips.csv"},
    )


@router.get("/breakdown")
def payslip_breakdown(
    year: int | None = None, category: str = "deduction", db: Session = Depends(get_db)
):
    query = db.query(models.PayslipItem.name, func.sum(models.PayslipItem.amount)).join(
        models.Payslip
    )
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
    return {"labels": labels, "data": data}


@router.get("/{payslip_id}", response_model=Payslip)
def get_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail="Not found")
    return payslip
