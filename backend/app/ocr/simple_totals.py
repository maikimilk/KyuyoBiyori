import re
from .strategy import BaseParser, OCRResult

TOTAL_PAT = re.compile(r"(支給合計|控除合計|差引支給額)[^\d\-]*([\-\d,()]+)")

def _clean(n: str) -> int:
    return int(n.replace(",", "").replace("(", "-").replace(")", ""))

def call_vision_api(content: bytes) -> str:
    """Placeholder Vision API call."""
    return content.decode('utf-8', errors='ignore')

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
        if any(v is None for v in (gross, deduction, net)):
            raise ValueError("Totals not found")
        return OCRResult(gross=gross, deduction=deduction, net=net, text=text)
