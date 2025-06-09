import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

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

from .. import database, models
from ..schemas import (
    Payslip,
    PayslipCreate,
    PayslipItem,
    PayslipPreview,
    PayslipUpdate,
    ReparseRequest,
)

router = APIRouter()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Characters to normalize (fullwidth to ascii)
_TRANS_TABLE = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "＋": "+",
        "－": "-",
        "（": "(",
        "）": ")",
        "，": ",",
        "￥": "",
        "¥": "",
    }
)

_deduction_keywords = ["税", "保険", "控除", "料", "差引", "保険料改定", "精算"]

# units that indicate quantities rather than monetary amounts
# "月" は給与明細のタイトルに自然に含まれるため除外する
QUANTITY_UNITS = ["日", "人", "時間", "回", "回数", "週"]
# pattern to detect attendance items such as "欠勤日数" or "残業時間"
ATTENDANCE_PATTERN = re.compile(r"(日数|時間|回数?|人|週)$")

GROSS_KEYS = ("gross", "総支給", "支給総額", "支給合計", "総支給額")
NET_KEYS = ("net", "手取り", "差引支給額")
DEDUCTION_KEYS = ("deduction", "控除合計")
TOTAL_KEYS = set(GROSS_KEYS) | set(NET_KEYS) | set(DEDUCTION_KEYS)
TOTAL_KEYWORDS = re.compile(r"(合計|累計|差引|総支給)")
_TOTAL_EXCLUDE = re.compile(r"(累計|対象額|非課税)")

# section boundaries and lines to skip when parsing
SECTION_BEGIN = {
    "支給項目": ("payment", "支給合計"),
    "控除項目": ("deduction", "控除合計"),
}
SKIP_PAT = re.compile(r"(標準報酬|保険料改定|対象額|累計|非課税)")

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
    # 半角カナ見出しへの耐性
    "ｼｷｭｳｺｳﾓｸ",
    "ｺｳｼﾞｮｳｺｳﾓｸ",
    "ｼｭｳｷﾞｮｳｺｳﾓｸ",
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
    "ｼｷｭｳｺｳﾓｸ": "payment",
    "ｺｳｼﾞｮｳｺｳﾓｸ": "deduction",
    "ｼｭｳｷﾞｮｳｺｳﾓｸ": "attendance",
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
    item_amount = re.compile(r"^([^\d]+?)[：:\s]+([^\s]+)$")
    item_attendance = re.compile(r"^([^\d]+?)[：:\s]+(\d+)(日|人|時間|回数?|週)$")
    item_attendance_inline = re.compile(r"^([^\d]+?)(\d+)(日|人|時間|回数?|週)$")
    amount_only = re.compile(r"^[\+\-−△▲]?\(?\d[\d,]*\)?$")
    value_with_unit = re.compile(r"^(\d+)\s*(日|人|時間|回数?|週)$")
    amount_first_pattern = re.compile(
        r"^[¥￥]?((?:\([\+\-−△▲]?\d[\d,]*\))|[\+\-−△▲]?\d[\d,]*)\s+(.+)$"
    )

    def _clean_amount(s: str) -> int:
        s = s.translate(_TRANS_TABLE)
        negative = False
        if s.startswith("(") and s.endswith(")"):
            negative = True
            s = s[1:-1]
        s = re.sub(rf"({'|'.join(QUANTITY_UNITS)})$", "", s)
        s = s.replace(",", "").replace("−", "-").replace("△", "-").replace("▲", "-")
        digits = re.sub(r"\D", "", s)
        if len(digits) > 9:
            raise ValueError("overflow")
        amount = int(s)
        if negative:
            amount = -amount
        return amount

    def _handle_total_line(label: str, amt: int) -> bool:
        """Handle strict total labels. Return True if consumed."""
        nonlocal gross, net, deduction
        if _TOTAL_EXCLUDE.search(label):
            return True
        if "支給合計" in label or "総支給" in label:
            if gross is None:
                gross = amt
            return True
        if "控除合計" in label and "差引" not in label:
            if deduction is None:
                deduction = amt
            return True
        if "差引支給額" in label or "手取り" in label:
            if net is None:
                net = amt
            return True
        if re.fullmatch(r"口座振込額[:：]?", label):
            if net is None:
                net = amt
            return True
        return False

    current_section = None
    until_marker: str | None = None
    pending_section: str | None = None
    pending_names: list[str] = []
    reset_sections = ("支給合計", "控除合計", "差引支給額")

    def parse_token_pairs(tokens: list[str]) -> bool:
        """Parse simple repeated name/amount pairs. Return True if handled."""
        nonlocal gross, net, deduction, current_section, pending_section, pending_names
        handled = False
        i = 0
        while i < len(tokens) - 1:
            if pending_section:
                current_section = pending_section
                pending_section = None
            name = tokens[i].rstrip("：:")
            next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
            if name in SECTION_MAP:
                pending_section = SECTION_MAP[name]
                i += 1
                continue
            if next_tok is None:
                cleaned = re.sub(r"\d+$", "", name)
                if (
                    cleaned
                    and cleaned not in KNOWN_METADATA_LABELS
                    and cleaned not in KNOWN_SECTION_LABELS
                ):
                    pending_names.append(cleaned)
                i += 1
                continue
            # unit before number pattern: "日 21 所定労働日数"
            if (
                name in QUANTITY_UNITS
                and i < len(tokens) - 2
                and re.fullmatch(r"\d+", tokens[i + 1])
            ):
                amount = int(tokens[i + 1])
                attendance[tokens[i + 2]] = amount
                handled = True
                i += 3
                continue
            # quantity with explicit unit separated by space
            if (
                i < len(tokens) - 2
                and re.fullmatch(r"\d+", tokens[i + 1])
                and tokens[i + 2] in QUANTITY_UNITS
            ):
                amount = int(tokens[i + 1])
                attendance[name] = amount
                handled = True
                i += 3
                continue

            if next_tok and re.fullmatch(r"[\-−△▲]?\d[\d,]*", next_tok):
                try:
                    amount = _clean_amount(next_tok)
                except ValueError:
                    i += 2
                    continue
                if pending_section:
                    current_section = pending_section
                    pending_section = None
                if name in TOTAL_KEYS:
                    if name in GROSS_KEYS:
                        gross = amount
                    if name in NET_KEYS:
                        net = amount
                    if name in DEDUCTION_KEYS:
                        deduction = amount
                else:
                    clean_name = re.sub(r"\d+$", "", name)
                    category = CATEGORY_MAP.get(clean_name) or (
                        "payment"
                        if current_section == "payment"
                        else "deduction" if current_section == "deduction" else None
                    )
                    if current_section != "attendance" and abs(amount) < 10:
                        logger.warning(
                            "Skipping suspicious small amount %s for %s",
                            amount,
                            clean_name,
                        )
                    else:
                        items.append(
                            PayslipItem(
                                name=clean_name,
                                amount=amount,
                                category=category,
                                section=current_section,
                            )
                        )
                handled = True
                i += 2
            else:
                m_comb = re.match(r"^([^\d]+?)([\-−△▲]?\d[\d,]*)$", name)
                if m_comb:
                    nm, val = m_comb.groups()
                    digits = re.sub(r"\D", "", val)
                    if "," in val or len(digits) >= 2:
                        try:
                            amount = _clean_amount(val)
                        except ValueError:
                            i += 1
                            continue
                    else:
                        cleaned = re.sub(r"\d+$", "", nm)
                        if (
                            cleaned
                            and cleaned not in KNOWN_METADATA_LABELS
                            and cleaned not in KNOWN_SECTION_LABELS
                        ):
                            pending_names.append(cleaned)
                            handled = True
                            i += 1
                            continue
                        i += 1
                        continue
                    if pending_section:
                        current_section = pending_section
                        pending_section = None
                    category = CATEGORY_MAP.get(nm) or (
                        "payment"
                        if current_section == "payment"
                        else "deduction" if current_section == "deduction" else None
                    )
                    items.append(
                        PayslipItem(
                            name=nm,
                            amount=amount,
                            category=category,
                            section=current_section,
                        )
                    )
                    handled = True
                    i += 1
                else:
                    i += 1
        return handled

    for raw_line in text.splitlines():
        line = raw_line.strip().translate(_TRANS_TABLE)
        if not line:
            continue

        # section handling
        matched_start = False
        for hdr, (sec, end) in SECTION_BEGIN.items():
            if line.startswith(hdr):
                current_section = sec
                until_marker = end
                remainder = re.sub(rf"^{re.escape(hdr)}[：:]*\s*", "", line)
                line = remainder
                matched_start = True
                break
        if matched_start and not line:
            continue
        if until_marker and line.startswith(until_marker):
            marker = until_marker
            current_section = None
            until_marker = None
            remainder = re.sub(rf"^{re.escape(marker)}[：:]*\s*", "", line)
            line = remainder
            if not line:
                continue

        if SKIP_PAT.search(line):
            continue

        if line in reset_sections:
            current_section = None
            pending_section = None
            pending_names.clear()
            continue

        matched_section = None
        remainder = ""
        for sec_label, sec_name in SECTION_MAP.items():
            m = re.match(rf"^{re.escape(sec_label)}(?:[：:]\s*|\s+)?(.*)$", line)
            if m and (not m.group(1) or m.group(1) != line):
                matched_section = sec_name
                remainder = m.group(1).strip()
                break
        if matched_section:
            if pending_section is None:
                pending_section = matched_section
            pending_names.clear()
            if not remainder:
                continue
            line = remainder

        if any(
            re.fullmatch(rf"{re.escape(lbl)}[：:]*\d*", line)
            for lbl in KNOWN_SECTION_LABELS
        ):
            cleaned = re.sub(r"[\d：:]+$", "", line.strip())
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
            if pending_section:
                current_section = pending_section
                pending_section = None
            name, value, _u = m_att.groups()
            attendance[name.strip()] = int(value)
            pending_names.clear()
            continue

        m_att_inline = item_attendance_inline.match(line)
        if m_att_inline:
            if pending_section:
                current_section = pending_section
                pending_section = None
            name, value, _u = m_att_inline.groups()
            attendance[name.strip()] = int(value)
            pending_names.clear()
            continue

        if line.count(" ") >= 3 and sum(ch.isdigit() for ch in line) >= 2:
            tokens = [t for t in re.split(r"\s+", line) if t]
            if parse_token_pairs(tokens):
                pending_names.clear()
                continue

        m = item_amount.match(line)
        if m:
            if pending_section:
                current_section = pending_section
                pending_section = None
            name, value = m.groups()
            name = re.sub(r"\d+$", "", name.strip())
            if not name or name in KNOWN_METADATA_LABELS:
                pending_names.clear()
                continue
            try:
                amount = _clean_amount(value)
            except ValueError:
                tokens = [t for t in re.split(r"\s+", line) if t]
                if parse_token_pairs(tokens):
                    pending_names.clear()
                    continue
                pending_names.clear()
                continue
            section = current_section
            if (
                section == "attendance"
                or ATTENDANCE_PATTERN.search(name)
                or name in QUANTITY_UNITS
            ):
                attendance[name] = amount
                pending_names.clear()
            elif name in TOTAL_KEYS:
                if name in GROSS_KEYS:
                    gross = amount
                if name in NET_KEYS:
                    net = amount
                if name in DEDUCTION_KEYS:
                    deduction = amount
            elif _handle_total_line(name, amount):
                pass
            else:
                if section != "attendance" and abs(amount) < 10:
                    logger.warning(
                        "Skipping suspicious small amount %s for %s", amount, name
                    )
                else:
                    category = (
                        "payment"
                        if section == "payment"
                        else "deduction" if section == "deduction" else None
                    )
                    items.append(
                        PayslipItem(
                            name=name, amount=amount, category=category, section=section
                        )
                    )
            pending_names.clear()
            continue

        if value_with_unit.match(line) and pending_names:
            if pending_section:
                current_section = pending_section
                pending_section = None
            v, _u = value_with_unit.match(line).groups()
            name = pending_names.pop(0)
            attendance[name] = int(v)
            pending_names.clear()
            continue

        if amount_only.match(line):
            if pending_names == ["支給合計"]:
                gross = _clean_amount(line)
                pending_names.clear()
                continue
            if pending_names == ["控除合計"]:
                deduction = _clean_amount(line)
                pending_names.clear()
                continue
            if pending_names:
                if pending_section:
                    current_section = pending_section
                    pending_section = None
                name = pending_names.pop(0)
                try:
                    amount = _clean_amount(line)
                except ValueError:
                    continue
                section = current_section
                if (
                    section == "attendance"
                    or ATTENDANCE_PATTERN.search(name)
                    or name in QUANTITY_UNITS
                ):
                    attendance[name] = amount
                    pending_names.clear()
                elif name in TOTAL_KEYS:
                    if name in GROSS_KEYS:
                        gross = amount
                    if name in NET_KEYS:
                        net = amount
                    if name in DEDUCTION_KEYS:
                        deduction = amount
                elif _handle_total_line(name, amount):
                    pass
                else:
                    if section != "attendance" and abs(amount) < 10:
                        logger.warning(
                            "Skipping suspicious small amount %s for %s", amount, name
                        )
                    else:
                        category = (
                            "payment"
                            if section == "payment"
                            else "deduction" if section == "deduction" else None
                        )
                        items.append(
                            PayslipItem(
                                name=name,
                                amount=amount,
                                category=category,
                                section=section,
                            )
                        )
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
            if pending_section:
                current_section = pending_section
                pending_section = None
            try:
                amount = _clean_amount(m_first.group(1))
            except ValueError:
                pending_names.clear()
                continue
            name = re.sub(r"\d+$", "", m_first.group(2).strip())
            if pending_names:
                prev_name = pending_names.pop(0)
                section_prev = current_section
                if (
                    section_prev == "attendance"
                    or ATTENDANCE_PATTERN.search(prev_name)
                    or prev_name in QUANTITY_UNITS
                ):
                    attendance[prev_name] = amount
                    pending_names.clear()
                elif prev_name in TOTAL_KEYS:
                    if prev_name in GROSS_KEYS:
                        gross = amount
                    if prev_name in NET_KEYS:
                        net = amount
                    if prev_name in DEDUCTION_KEYS:
                        deduction = amount
                elif _handle_total_line(prev_name, amount):
                    pass
                else:
                    if section_prev != "attendance" and abs(amount) < 10:
                        logger.warning(
                            "Skipping suspicious small amount %s for %s",
                            amount,
                            prev_name,
                        )
                    else:
                        category_prev = (
                            "payment"
                            if section_prev == "payment"
                            else "deduction" if section_prev == "deduction" else None
                        )
                        items.append(
                            PayslipItem(
                                name=prev_name,
                                amount=amount,
                                category=category_prev,
                                section=section_prev,
                            )
                        )
                if name and name not in KNOWN_METADATA_LABELS:
                    pending_names.append(name)
                continue

            if not name or name in KNOWN_METADATA_LABELS:
                pending_names.clear()
                continue
            section = current_section
            if (
                section == "attendance"
                or ATTENDANCE_PATTERN.search(name)
                or name in QUANTITY_UNITS
            ):
                attendance[name] = amount
            elif name in TOTAL_KEYS:
                if name in GROSS_KEYS:
                    gross = amount
                if name in NET_KEYS:
                    net = amount
                if name in DEDUCTION_KEYS:
                    deduction = amount
            elif _handle_total_line(name, amount):
                pass
            else:
                if section != "attendance" and abs(amount) < 10 and not pending_names:
                    logger.warning(
                        "Skipping suspicious small amount %s for %s", amount, name
                    )
                else:
                    category = (
                        "payment"
                        if section == "payment"
                        else "deduction" if section == "deduction" else None
                    )
                    items.append(
                        PayslipItem(
                            name=name, amount=amount, category=category, section=section
                        )
                    )
            continue

        if re.match(r"^[^\d]+$", line):
            cleaned = re.sub(r"\d+$", "", line.strip())
            if (
                cleaned
                and cleaned not in KNOWN_METADATA_LABELS
                and cleaned not in KNOWN_SECTION_LABELS
            ):
                pending_names.append(cleaned)
            continue

        # Token-based fallback with name/amount pair queuing
        tokens = [t for t in re.split(r"\s+", line) if t]
        if tokens:
            if parse_token_pairs(tokens):
                pending_names.clear()
                continue
            name_queue = pending_names[:]
            pending_names = []
            handled = False
            i = 0
            while i < len(tokens):
                if pending_section:
                    current_section = pending_section
                    pending_section = None
                token = tokens[i]
                m_val = value_with_unit.match(token)
                if m_val:
                    if name_queue:
                        if pending_section:
                            current_section = pending_section
                            pending_section = None
                        v, _u = m_val.groups()
                        name = name_queue.pop(0)
                        attendance[name] = int(v)
                        pending_names.clear()
                        name_queue.clear()
                        handled = True
                    i += 1
                    continue

                if (
                    amount_only.match(token)
                    and i + 1 < len(tokens)
                    and tokens[i + 1] in QUANTITY_UNITS
                    and name_queue
                ):
                    if pending_section:
                        current_section = pending_section
                        pending_section = None
                    name = name_queue.pop(0)
                    attendance[name] = _clean_amount(token)
                    pending_names.clear()
                    name_queue.clear()
                    handled = True
                    i += 2
                    continue

                if amount_only.match(token):
                    if name_queue:
                        if pending_section:
                            current_section = pending_section
                            pending_section = None
                        name = name_queue.pop(0)
                        try:
                            amount = _clean_amount(token)
                        except ValueError:
                            i += 1
                            continue
                        section = current_section
                        if (
                            section == "attendance"
                            or ATTENDANCE_PATTERN.search(name)
                            or name in QUANTITY_UNITS
                        ):
                            attendance[name] = amount
                        elif name in TOTAL_KEYS:
                            if name in GROSS_KEYS:
                                gross = amount
                            if name in NET_KEYS:
                                net = amount
                            if name in DEDUCTION_KEYS:
                                deduction = amount
                        elif _handle_total_line(name, amount):
                            pass
                        else:
                            if section != "attendance" and abs(amount) < 10:
                                logger.warning(
                                    "Skipping suspicious small amount %s for %s",
                                    amount,
                                    name,
                                )
                            else:
                                category = (
                                    "payment"
                                    if section == "payment"
                                    else "deduction" if section == "deduction" else None
                                )
                                items.append(
                                    PayslipItem(
                                        name=name,
                                        amount=amount,
                                        category=category,
                                        section=section,
                                    )
                                )
                        handled = True
                    else:
                        try:
                            amount = _clean_amount(token)
                        except ValueError:
                            i += 1
                            continue
                        if abs(amount) >= 10:
                            logger.warning("Amount without item name: %s", token)
                    i += 1
                    continue

                m_name_amount = re.match(r"^([^\d]+?)([\-−△▲]?\d[\d,]*)$", token)
                if m_name_amount:
                    name, val = m_name_amount.groups()
                    digits = re.sub(r"\D", "", val)
                    if (
                        ("," in val or len(digits) >= 2)
                        and name
                        and name not in KNOWN_METADATA_LABELS
                        and name not in KNOWN_SECTION_LABELS
                    ):
                        if pending_section:
                            current_section = pending_section
                            pending_section = None
                        section = current_section
                        try:
                            amount = _clean_amount(val)
                        except ValueError:
                            i += 1
                            continue
                        category = (
                            "payment"
                            if section == "payment"
                            else "deduction" if section == "deduction" else None
                        )
                        items.append(
                            PayslipItem(
                                name=name,
                                amount=amount,
                                category=category,
                                section=section,
                            )
                        )
                        handled = True
                        i += 1
                        continue
                    # treat as just a name token if the numeric part is likely an index

                cleaned = re.sub(r"\d+$", "", token)
                if (
                    cleaned
                    and cleaned not in KNOWN_METADATA_LABELS
                    and cleaned not in KNOWN_SECTION_LABELS
                ):
                    name_queue.append(cleaned)
                    handled = True
                i += 1

            pending_names.extend(name_queue)
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
            if it.amount < 0:
                category = "deduction"
            elif it.section == "attendance" or ATTENDANCE_PATTERN.search(it.name):
                category = "attendance"
            elif any(k in it.name for k in _deduction_keywords):
                category = "deduction"
            else:
                category = "payment"
            if it.name not in CATEGORY_MAP:
                logger.info(
                    "Unknown item name encountered: %s -> %s", it.name, category
                )
        if category in ("skip", "attendance"):
            continue
        if category == "payment" and any(k in it.name for k in _deduction_keywords):
            category = "deduction"
        if category != "attendance" and (
            it.section == "attendance" or ATTENDANCE_PATTERN.search(it.name)
        ):
            category = "attendance"
        section = it.section or (
            "attendance"
            if category == "attendance"
            else (
                "payment"
                if category == "payment"
                else "deduction" if category == "deduction" else None
            )
        )
        categorized.append(
            PayslipItem(
                id=it.id,
                name=it.name,
                amount=it.amount,
                category=category,
                section=section,
            )
        )
    return categorized


def _post_process_totals(parsed: dict) -> None:
    """Fill missing total amounts based on other values."""
    gross = parsed.get("gross_amount")
    net = parsed.get("net_amount")
    deduction = parsed.get("deduction_amount")
    if net is None and gross is not None and deduction is not None:
        parsed["net_amount"] = gross - deduction


def _recalc_totals(payslip_dict: dict) -> None:
    """Recalculate totals from items.

    Items coming from the front-end may lack a ``category`` field.  In that
    case we fall back to judging by the amount's sign.  If no payment or
    deduction entries are found we keep the existing values to avoid
    overwriting them with zeroes.
    """

    def _get(it, key):
        return it.get(key) if isinstance(it, dict) else getattr(it, key, None)

    payments: list[int] = []
    deductions: list[int] = []
    for it in payslip_dict.get("items", []):
        amt = _get(it, "amount") or 0
        cat = (_get(it, "category") or "").lower()
        if cat == "payment" or (not cat and amt >= 0):
            payments.append(amt)
        elif cat == "deduction" or (not cat and amt < 0):
            deductions.append(abs(amt))

    if payments:
        payslip_dict["gross_amount"] = sum(payments)
    if deductions:
        payslip_dict["deduction_amount"] = sum(deductions)
    payslip_dict["net_amount"] = payslip_dict.get("gross_amount", 0) - payslip_dict.get("deduction_amount", 0)


def _normalize_items(items: list[PayslipItem]) -> tuple[list[PayslipItem], list[PayslipItem]]:
    """Return payment and deduction lists with negative amounts treated as deductions."""
    payments: list[PayslipItem] = []
    deductions: list[PayslipItem] = []
    for it in items:
        target = deductions if (it.amount < 0 or it.category == "deduction") else payments
        target.append(it)
    return payments, deductions


def _consistency_check(
    payments: list[PayslipItem],
    deductions: list[PayslipItem],
    gross: int | None,
    net: int | None,
) -> list[str]:
    pay_sum = sum(i.amount for i in payments)
    ded_sum = sum(i.amount for i in deductions)
    errors: list[str] = []
    if gross is not None and abs(pay_sum - gross) > 1:
        errors.append(f"支給内訳合計({pay_sum}) ≠ 支給合計行({gross})")
    if net is not None and abs((pay_sum - ded_sum) - net) > 1:
        errors.append("支給－控除 と 差引支給額 が一致しません")
    return errors


def _warn_inconsistent(gross: int | None, deduction: int | None, net: int | None) -> list[str]:
    warnings: list[str] = []
    if gross is not None and deduction is not None and net is not None:
        if gross - deduction != net:
            warnings.append("支給合計 - 控除合計 と 差引支給額 が一致しません")
    return warnings


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
    payments, deductions = _normalize_items(parsed["items"])

    gross = parsed.get("gross_amount")
    deduction = parsed.get("deduction_amount")
    net = parsed.get("net_amount")

    if gross is None:
        gross = sum(i.amount for i in payments)
        parsed["gross_amount"] = gross
    if deduction is None:
        deduction = sum(i.amount for i in deductions)
        parsed["deduction_amount"] = deduction
    if net is None:
        net = gross - deduction
        parsed["net_amount"] = net

    warnings = _warn_inconsistent(gross, deduction, net)
    for w in warnings:
        logger.warning(w)
    parsed["warnings"] = warnings
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


def _to_iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _schema_from_model(p: models.Payslip) -> Payslip:
    return Payslip(
        id=p.id,
        filename=p.filename,
        date=_to_iso(p.date),
        type=p.type,
        gross_amount=p.gross_amount or 0,
        net_amount=p.net_amount or 0,
        deduction_amount=p.deduction_amount or 0,
        items=[
            PayslipItem(
                id=it.id,
                name=it.name,
                amount=it.amount,
                category=it.category,
                section=it.section,
            )
            for it in p.items
        ],
    )


@router.post("/upload", response_model=PayslipPreview)
async def upload_payslip(
    file: UploadFile = File(...),
):
    content = await file.read()
    parsed = _parse_file(content)
    _recalc_totals(parsed)
    slip_type = _detect_slip_type(parsed.get("text", ""))
    return PayslipPreview(
        filename=file.filename,
        date=_to_iso(parsed.get("date")),
        type=slip_type,
        gross_amount=parsed.get("gross_amount"),
        net_amount=parsed.get("net_amount"),
        deduction_amount=parsed.get("deduction_amount"),
        items=parsed["items"],
        warnings=parsed.get("warnings"),
    )


@router.post("/save", response_model=Payslip)
def save_payslip(data: PayslipCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    logger.info(
        "SAVE incoming: gross=%s ded=%s net=%s",
        payload.get("gross_amount"),
        payload.get("deduction_amount"),
        payload.get("net_amount"),
    )
    _recalc_totals(payload)
    logger.info(
        "SAVE fixed: gross=%s ded=%s net=%s",
        payload["gross_amount"],
        payload["deduction_amount"],
        payload["net_amount"],
    )

    date_obj = _parse_date(payload.get("date"))
    net = payload["net_amount"]
    exists = (
        db.query(models.Payslip)
        .filter_by(date=date_obj, type=payload.get("type"), net_amount=net)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="同じ明細が既に登録されています")

    payslip = models.Payslip(
        filename=payload["filename"],
        date=date_obj,
        type=payload.get("type"),
        gross_amount=payload["gross_amount"],
        net_amount=payload["net_amount"],
        deduction_amount=payload["deduction_amount"],
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
    return _schema_from_model(payslip)


@router.get("/", response_model=list[Payslip])
def list_payslips(db: Session = Depends(get_db)):
    records = db.query(models.Payslip).all()
    return [_schema_from_model(p) for p in records]


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
    records = query.all()
    return [_schema_from_model(p) for p in records]


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
    payload = data.model_dump()
    logger.info(
        "SAVE incoming: gross=%s ded=%s net=%s",
        payload.get("gross_amount"),
        payload.get("deduction_amount"),
        payload.get("net_amount"),
    )
    _recalc_totals(payload)
    logger.info(
        "SAVE fixed: gross=%s ded=%s net=%s",
        payload["gross_amount"],
        payload["deduction_amount"],
        payload["net_amount"],
    )

    payslip.filename = payload["filename"]
    payslip.date = _parse_date(payload.get("date"))
    payslip.type = payload.get("type")
    payslip.gross_amount = payload["gross_amount"]
    payslip.net_amount = payload["net_amount"]
    payslip.deduction_amount = payload["deduction_amount"]
    payslip.items.clear()
    for it in data.items:
        payslip.items.append(
            models.PayslipItem(name=it.name, amount=it.amount, category=it.category)
        )
    db.commit()
    db.refresh(payslip)
    return _schema_from_model(payslip)


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
    deduction_this_month = sum_amount([p.deduction_amount for p in this_month])
    net_prev_month = sum_amount([p.net_amount for p in prev_month])
    bonus_total = sum_amount([p.net_amount for p in bonus])

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
    if all(v == 0 for v in data):
        return {"labels": [], "data": []}
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
    query = db.query(models.PayslipItem.name, models.PayslipItem.amount, models.PayslipItem.category).join(
        models.Payslip
    )
    if year:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        query = query.filter(models.Payslip.date >= start, models.Payslip.date <= end)
    items = query.all()
    payments: dict[str, int] = {}
    deductions: dict[str, int] = {}
    for name, amount, cat in items:
        target = deductions if (amount < 0 or cat == "deduction") else payments
        target[name] = target.get(name, 0) + amount
    selected = deductions if category == "deduction" else payments
    labels = list(selected.keys())
    data = [selected[k] for k in labels]
    return {"labels": labels, "data": data}


@router.get("/{payslip_id}", response_model=Payslip)
def get_payslip(payslip_id: int, db: Session = Depends(get_db)):
    payslip = db.query(models.Payslip).get(payslip_id)
    if not payslip:
        raise HTTPException(status_code=404, detail="Not found")
    return _schema_from_model(payslip)
