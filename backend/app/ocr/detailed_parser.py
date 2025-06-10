import os
import base64
import json
import requests

from .strategy import BaseParser, OCRResult
from ..domain.item import Item


class DetailedParser(BaseParser):
    def parse(self, content: bytes, mode: str = "detailed") -> OCRResult:
        assert mode == "detailed", "DetailedParser only supports detailed mode"

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        image_b64 = base64.b64encode(content).decode()

        prompt = (
            "You are an expert document parser.\n"
            "Extract the following fields from the payslip image:\n"
            "- Gross amount (支給合計 or 総支給額)\n"
            "- Deduction amount (控除合計)\n"
            "- Net amount (差引支給額 or 手取額)\n"
            "- List of items:\n"
            "  - For each 支給項目 and 控除項目, return {name, amount, category(\"支給\"/\"控除\")}\n"
            "Return a JSON object:\n"
            "{\n"
            "  \"gross\": int,\n"
            "  \"deduction\": int,\n"
            "  \"net\": int,\n"
            "  \"items\": [ { \"name\": string, \"amount\": int, \"category\": \"支給\" | \"控除\" } ... ]\n"
            "}"
        )

        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key="
            + api_key,
            json={
                "contents": [
                    {"parts": [{"text": prompt}]},
                    {"parts": [{"inlineData": {"mimeType": "image/jpeg", "data": image_b64}}]},
                ]
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(raw_text)

        return OCRResult(
            gross=parsed["gross"],
            deduction=parsed["deduction"],
            net=parsed["net"],
            text="[Gemini parsed]",
            items=[Item(**item) for item in parsed.get("items", [])],
        )
