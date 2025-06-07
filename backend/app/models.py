from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Payslip(Base):
    __tablename__ = 'payslips'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=True)
    type = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    gross_amount = Column(Integer, nullable=True)
    net_amount = Column(Integer, nullable=True)
    deduction_amount = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
