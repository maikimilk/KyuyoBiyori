from pydantic import BaseModel
from typing import Optional

class PayslipPreview(BaseModel):
    filename: str
    gross: int
    deduction: int
    net: int
    warnings: list[str] | None = None

class PayslipCreate(BaseModel):
    filename: str
    date: Optional[str] = None
    type: Optional[str] = None
    gross: int
    deduction: int
    net: int

class PayslipRead(PayslipCreate):
    id: int
