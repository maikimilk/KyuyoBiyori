import re
import base64
import os
from .strategy import BaseParser, OCRResult

# allow matching of normal and full-width digits
TOTAL_PAT = re.compile(
    r"(支給合計|控除合計|差引支給額)[^\d０-９\-]*([\-\d０-９,，()]+)"
)

_FW_TO_ASCII = str.maketrans("０１２３４５６７８９－", "0123456789-")


def _normalize_digits(s: str) -> str:
    """Convert full-width digits and minus sign to ASCII equivalents."""
    return s.translate(_FW_TO_ASCII)


def _clean(n: str) -> int:
    n = _normalize_digits(n)
    return int(n.replace(",", "").replace("，", "").replace("(", "-").replace(")", ""))

def call_vision_api(content: bytes) -> str:
    """Return text from given image/PDF content using Google Cloud Vision API.

    If `GCLOUD_API_KEY` (or `NEXT_PUBLIC_GCLOUD_API_KEY`) is not set, this
    function simply decodes the bytes as UTF-8 and returns the result. This
    keeps unit tests offline while enabling real OCR when an API key is
    provided.
    """

    api_key = os.getenv("GCLOUD_API_KEY") or os.getenv("NEXT_PUBLIC_GCLOUD_API_KEY")
    if not api_key:
        return content.decode("utf-8", errors="ignore")

    try:
        import requests  # imported lazily to avoid hard dependency during tests
    except Exception as e:  # pragma: no cover - optional dependency
        raise RuntimeError("requests library is required for OCR") from e

    endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(content).decode()},
                "features": [{"type": "TEXT_DETECTION"}],
            }
        ]
    }
    resp = requests.post(endpoint, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data["responses"][0].get("fullTextAnnotation", {}).get("text", "")

class TotalsOnlyParser(BaseParser):
    def parse(self, content: bytes) -> OCRResult:
        text = call_vision_api(content)
        gross = deduction = net = None
        for m in TOTAL_PAT.finditer(text):
            key, val = m.group(1), _clean(m.group(2))
            if "支給合計" in key:
                gross = val
            elif "控除合計" in key:
                deduction = val
            elif "差引支給額" in key:
                net = val
        if gross is None and net is not None and deduction is not None:
            gross = net + deduction
        if deduction is None and gross is not None and net is not None:
            deduction = gross - net
        if net is None and gross is not None and deduction is not None:
            net = gross - deduction
        if any(v is None for v in (gross, deduction, net)):
            raise ValueError("Totals not found")
        return OCRResult(gross=gross, deduction=deduction, net=net, text=text)
