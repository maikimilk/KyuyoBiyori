from datetime import date
from pydantic import BaseModel, Field
from typing import List, Optional

from .item import Item

class Payslip(BaseModel):
    id: Optional[int] = None
    date: Optional[date] = None
    type: Optional[str] = None  # salary / bonus
    gross: int = 0
    deduction: int = 0
    net: int = 0
    # --- OPTIONAL 将来用 ---
    items: List[Item] = Field(default_factory=list)
