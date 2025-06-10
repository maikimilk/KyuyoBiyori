import os
import base64
import json
import requests

from .strategy import BaseParser, OCRResult
from ..domain.item import Item

PROMPT = """
You are an expert document parser.

You will be given an image of a Japanese payslip.
The payslip may be:
- a scanned paper document
- a photo of a paper payslip
- a screenshot of an HR system (e.g. Jobcan)
- a PDF export of a digital payslip

Your task is to extract the following structured information:

* Gross amount (支給合計 / 総支給額 / 当月総支給額累計)
* Deduction amount (控除合計)
* Net amount (差引支給額 / 手取額 / 口座振込額)
* Paid leave remaining days (年休残 / 有給休暇残日数 / 年休残（日） / 年休残数)
* Total paid leave granted this year (年休数 / 年休日数 / 有給付与日数 / 年休数（日）)
* List of payment and deduction items:
  * For each entry under 支給項目 (payments) and 控除項目 (deductions), return:
    * { "name": string, "amount": int, "category": "支給" | "控除" }

Return the result strictly in the following JSON format:

```json
{
  "gross": int,
  "deduction": int,
  "net": int,
  "paid_leave_remaining_days": float | null,
  "total_paid_leave_days": float | null,
  "items": [
    { "name": string, "amount": int, "category": "支給" | "控除" }
  ]
}
Additional instructions:

Normalize all Japanese full-width numbers and minus signs to standard half-width digits.

Convert all amounts to integers (no commas).

If any field such as paid leave days is missing, return null.

The 支給項目 and 控除項目 blocks may appear side-by-side or vertically stacked.

Ignore unrelated sections such as remarks, social insurance cumulative info, totals across months, etc.

If the item name includes parentheses (e.g., "その他(非課)"), include the full name as-is.

Focus only on the content area of the payslip. Ignore surrounding UI or footer/toolbars from screenshots.

Examples of common patterns:

支給項目 block may include: 基本給, 通勤補助, その他手当, etc.

控除項目 block may include: 所得税, 健康保険料, 厚生年金保険料, etc.

Net amount may be shown as 差引支給額 or 口座振込額 — treat them the same.

Please analyze the image and return structured output accordingly.
"""

class DetailedParser(BaseParser):
def parse(self, content: bytes, mode: str = "detailed") -> OCRResult:
assert mode == "detailed", "DetailedParser only supports detailed mode"
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    image_b64 = base64.b64encode(content).decode()

    print("DEBUG Gemini API call starting...")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "parts": [
                    { "text": PROMPT },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ]
    }

    resp = requests.post(endpoint, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    print("DEBUG Gemini raw response:", json.dumps(data, ensure_ascii=False, indent=2))

    # Extract the first candidate text content
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

    # Clean potential code fences ```json ... ``` that Gemini sometimes adds
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    print("DEBUG Gemini parsed text:", raw_text)

    parsed = json.loads(raw_text)

    return OCRResult(
        gross=parsed["gross"],
        deduction=parsed["deduction"],
        net=parsed["net"],
        text="[Gemini parsed]",
        warnings=None,
        items=[
            Item(**item)
            for item in parsed.get("items", [])
        ],
    )
