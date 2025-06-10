import re
import os
from ..domain.item import Item
from .strategy import BaseParser, OCRResult

# allow matching of normal and full-width digits
TOTAL_PAT = re.compile(
    r"(支給合計|総支給額|控除合計|控除額|差引支給額|差引支給|手取り|手取額)[^\d０-９\-]*([\-\d０-９,，()]+)"
)


_FW_TO_ASCII = str.maketrans("０１２３４５６７８９－", "0123456789-")


def _normalize_digits(s: str) -> str:
    """Convert full-width digits and minus sign to ASCII equivalents."""
    return s.translate(_FW_TO_ASCII)


def _clean(n: str) -> int:
    n = _normalize_digits(n)
    return int(n.replace(",", "").replace("，", "").replace("(", "-").replace(")", ""))

# --- item parsing helpers ---
LINE_ITEM_PAT = re.compile(r"^(.*?)\s*([\-\d０-９,，()]+)$")


def _parse_items(text: str) -> list[Item]:
    lines = text.splitlines()
    items: list[Item] = []
    mode = None  # None, "支給", "控除"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "支給項目" in line:
            mode = "支給"
            continue
        if "控除項目" in line:
            mode = "控除"
            continue
        if any(word in line for word in ["就業項目", "支給合計", "控除合計", "差引支給額"]):
            mode = None
            continue

        if mode in ("支給", "控除"):
            m = LINE_ITEM_PAT.match(line)
            if m:
                name, amount_str = m.group(1), _clean(m.group(2))
                items.append(Item(name=name.strip(), amount=amount_str, category=mode))
    return items

def call_vision_api(content: bytes) -> str:
    """Return text from given image/PDF content using Google Cloud Vision API.
    
    If GOOGLE_APPLICATION_CREDENTIALS is set, uses google-cloud-vision library.
    If not set, returns dummy OCR text (for offline testing).
    """

    # 優先的に GOOGLE_APPLICATION_CREDENTIALS を使う
    # ない場合はテスト用に content を直接デコードして返す
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return content.decode("utf-8", errors="ignore")

    try:
        from google.cloud import vision
    except Exception as e:
        raise RuntimeError("google-cloud-vision library is required for OCR") from e

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    texts = response.text_annotations
    if not texts:
        return ""
    return texts[0].description


class TotalsOnlyParser(BaseParser):
    def parse(self, content: bytes) -> OCRResult:
        text = call_vision_api(content)
        
        print("DEBUG OCR TEXT >>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        print(text)
        print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")

        # さらに１行ごとの確認（マッチしなかった候補を見る用）
        lines = text.splitlines()
        for line in lines:
            if any(keyword in line for keyword in ["支給", "総支給", "控除", "差引", "手取"]):
                print("DEBUG CANDIDATE LINE:", line)
        
        gross = deduction = net = None
        for m in TOTAL_PAT.finditer(text):
            print(f"DEBUG MATCHED: {m.group(1)} → {m.group(2)}")  # ← debug 追加
            key, val = m.group(1), _clean(m.group(2))
            if "支給" in key and "合計" in key:
                gross = val
            elif "控除" in key and "合計" in key:
                deduction = val
            elif "差引" in key:
                net = val

        if gross is None and net is not None and deduction is not None:
            gross = net + deduction
        if deduction is None and gross is not None and net is not None:
            deduction = gross - net
        if net is None and gross is not None and deduction is not None:
            net = gross - deduction
        if any(v is None for v in (gross, deduction, net)):
            raise ValueError("Totals not found")

        items = _parse_items(text)

        return OCRResult(gross=gross, deduction=deduction, net=net, text=text, items=items)

