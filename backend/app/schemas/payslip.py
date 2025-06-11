from pydantic import BaseModel
from typing import List, Optional

class PayslipItemSchema(BaseModel):
    name: str
    amount: int
    category: str

class PayslipCreate(BaseModel):
    filename: str
    date: Optional[str] = None
    type: Optional[str] = None
    gross_amount: int
    deduction_amount: int
    net_amount: int
    items: List[PayslipItemSchema] = []

class PayslipPreview(BaseModel):
    filename: str
    type: Optional[str] = None
    gross_amount: int
    deduction_amount: int
    net_amount: int
    paid_leave_remaining_days: Optional[float] = None
    total_paid_leave_days: Optional[float] = None
    warnings: Optional[List[str]] = None
    items: List[PayslipItemSchema] = []

class PayslipRead(PayslipCreate):
    id: int
