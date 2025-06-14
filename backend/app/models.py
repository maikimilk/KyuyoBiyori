from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
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
    paid_leave_remaining_days = Column(Float, nullable=True)
    total_paid_leave_days = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("PayslipItem", back_populates="payslip", cascade="all, delete-orphan")


class PayslipItem(Base):
    __tablename__ = 'payslip_items'

    id = Column(Integer, primary_key=True, index=True)
    payslip_id = Column(Integer, ForeignKey('payslips.id'))
    name = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    category = Column(String, nullable=True)

    payslip = relationship("Payslip", back_populates="items")
