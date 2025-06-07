from pydantic import BaseModel

class PayslipBase(BaseModel):
    filename: str

class PayslipCreate(PayslipBase):
    pass

class Payslip(PayslipBase):
    id: int

    class Config:
        orm_mode = True
