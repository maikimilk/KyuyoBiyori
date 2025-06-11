import os
import base64
import json
import requests
from typing import List, Optional
import re
from .strategy import BaseParser, OCRResult
from ..domain.item import Item

# ------------ 解析プロンプト ------------ #
PROMPT = r"""
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
  type": "salary" | "bonus",
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

# ------------ Gemini API 連携設定 ------------ #
API_ENDPOINT = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-2.0-flash:generateContent?key={key}"
)

# ---- 追加： safe_json_extract ----
def safe_json_extract(raw_text: str) -> str:
    """Remove code fences and leading 'json\n' if present"""
    raw_text = raw_text.strip()
    # Remove ```json ... ``` markers
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]

    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    # Skip to first '{'
    json_start = raw_text.find("{")
    if json_start >= 0:
        raw_text = raw_text[json_start:]

    return raw_text

class DetailedParser(BaseParser):
    """Gemini-2.0-flash を用いた詳細パーサ"""

    def parse(self, content: bytes, mode: str = "detailed") -> OCRResult:
        if mode != "detailed":
            raise ValueError("DetailedParser supports only detailed mode")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        # ---- 画像を Base64 で埋め込む ----
        image_b64 = base64.b64encode(content).decode()

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": PROMPT},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ]
        }

        endpoint = API_ENDPOINT.format(key=api_key)
        resp = requests.post(endpoint, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        # ---- Gemini からのテキスト抽出 ----
        try:
            raw_text = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )
        except (KeyError, IndexError) as exc:
            raise RuntimeError("Gemini API response shape changed") from exc

        # ---- safe_json_extract 使用 ----
        raw_text = safe_json_extract(raw_text)

        # ---- JSON 解析 ----
        print("DEBUG GEMINI RAW TEXT:", raw_text)

        parsed = json.loads(raw_text)

        # ---- items 配列を安全に構築 ----
        items: Optional[List[Item]] = None
        if isinstance(parsed.get("items"), list):
            items = [Item(**it) for it in parsed["items"] if it.get("name")]

        return OCRResult(
            type=parsed.get("type"),
            gross=int(parsed["gross"]),
            deduction=int(parsed["deduction"]),
            net=int(parsed["net"]),
            text="[Gemini parsed]",
            paid_leave_remaining_days=parsed.get("paid_leave_remaining_days"),
            total_paid_leave_days=parsed.get("total_paid_leave_days"),
            warnings=None,
            items=[it.model_dump() for it in items] if items else None,
        )

