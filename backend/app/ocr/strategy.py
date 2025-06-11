from dataclasses import dataclass
from typing import List, Optional

from ..domain.item import Item

@dataclass
class OCRResult:
    gross: int
    deduction: int
    net: int
    text: str
    type: Optional[str] = None
    warnings: list[str] | None = None
    items: Optional[List[Item]] = None

class BaseParser:
    def parse(self, content: bytes, mode: str = "simple") -> OCRResult:
        """Parse payslip content.

        Parameters
        ----------
        content: bytes
            Raw file content to parse.
        mode: str
            Parsing mode. ``"simple"`` is the default and should keep
            backward compatibility.
        """
        raise NotImplementedError
