from pydantic import BaseModel
from typing import Literal

class PayslipBase(BaseModel):
    filename: str
    date: str | None = None
    type: str | None = None
    gross_amount: int | None = None
    net_amount: int | None = None
    deduction_amount: int | None = None

class PayslipItem(BaseModel):
    id: int | None = None
    name: str
    amount: int
    category: Literal['payment', 'deduction', 'net', 'attendance', 'skip'] | None = None
    section: str | None = None

class PayslipPreview(PayslipBase):
    items: list[PayslipItem] = []

class PayslipCreate(PayslipBase):
    items: list[PayslipItem] = []

class PayslipUpdate(PayslipBase):
    id: int
    items: list[PayslipItem] = []

class ReparseRequest(BaseModel):
    items: list[PayslipItem]

class Payslip(PayslipBase):
    id: int
    items: list[PayslipItem] = []

    model_config = {
        "from_attributes": True,
    }
