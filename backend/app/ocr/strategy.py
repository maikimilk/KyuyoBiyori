from dataclasses import dataclass

@dataclass
class OCRResult:
    gross: int
    deduction: int
    net: int
    text: str
    warnings: list[str] | None = None

class BaseParser:
    def parse(self, content: bytes) -> OCRResult:
        raise NotImplementedError
