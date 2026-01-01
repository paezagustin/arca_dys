from sqlalchemy import Column, Integer, ForeignKey
from app.core.database import Base


class PaymentInvoice(Base):
    __tablename__ = "payment_invoice"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
