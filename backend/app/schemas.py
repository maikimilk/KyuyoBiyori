from pydantic import BaseModel

class PayslipBase(BaseModel):
    filename: str
    date: str | None = None
    type: str | None = None
    gross_amount: int | None = None
    net_amount: int | None = None
    deduction_amount: int | None = None

class PayslipCreate(PayslipBase):
    pass

class Payslip(PayslipBase):
    id: int

    class Config:
        orm_mode = True
