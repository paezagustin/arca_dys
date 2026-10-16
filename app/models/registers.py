"""Registros simples, sin cuentas corrientes ni cálculo de nómina."""
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, Numeric, Enum, Index, CheckConstraint, false
from app.core.database import Base

EMPLOYEES = ("Francisco", "Juan Cruz")
SALARY_MEDIA = ("efectivo", "mercado pago")


class SalaryPayment(Base):
    __tablename__ = "salary_payments"
    __table_args__ = (CheckConstraint("amount>0", name="ck_salary_amount"),
        Index("ix_salary_date", "entry_date", "id"), Index("ix_salary_employee_date", "employee", "entry_date"))
    id = Column(Integer, primary_key=True)
    entry_key = Column(String(36), nullable=False, unique=True)
    entry_date = Column(Date, nullable=False)
    employee = Column(Enum(*EMPLOYEES, name="salary_employee"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    medium = Column(Enum(*SALARY_MEDIA, name="salary_medium"), nullable=False, server_default="mercado pago")
    version = Column(Integer, nullable=False, default=1)


class CustomerCredit(Base):
    __tablename__ = "customer_credits"
    __table_args__ = (CheckConstraint("amount>0", name="ck_credit_amount"),
        CheckConstraint("paid OR paid_date IS NULL", name="ck_credit_payment_date"),
        Index("ix_credit_paid_date", "paid", "entry_date", "id"))
    id = Column(Integer, primary_key=True)
    entry_key = Column(String(36), nullable=False, unique=True)
    customer = Column(String(150), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    observation = Column(Text, nullable=False, default="")
    entry_date = Column(Date, nullable=False)
    paid = Column(Boolean, nullable=False, server_default=false())
    paid_date = Column(Date)
    version = Column(Integer, nullable=False, default=1)
