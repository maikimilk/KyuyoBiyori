from dataclasses import dataclass
from typing import List, Optional

from ..domain.item import Item

@dataclass
class OCRResult:
    gross: int
    deduction: int
    net: int
    text: str
    warnings: list[str] | None = None
    items: Optional[List[Item]] = None

class BaseParser:
    def parse(self, content: bytes) -> OCRResult:
        raise NotImplementedError
