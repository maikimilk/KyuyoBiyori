from pydantic import BaseModel
from typing import Optional

class PayslipPreview(BaseModel):
    filename: str
    gross_amount: int
    deduction_amount: int
    net_amount: int
    warnings: list[str] | None = None
    items: list[dict] = []

class PayslipCreate(BaseModel):
    filename: str
    date: Optional[str] = None
    type: Optional[str] = None
    gross_amount: int
    deduction_amount: int
    net_amount: int

class PayslipRead(PayslipCreate):
    id: int
