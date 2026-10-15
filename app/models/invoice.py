from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, Index
from datetime import datetime
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (Index("invoices_invoice_number_key", "invoice_number", unique=True), Index("ix_invoices_date", "invoice_date", "id"))

    id = Column(Integer, primary_key=True, index=True)

    invoice_number = Column(String(300), nullable=True)
    total_amount = Column(Float, nullable=True)

    status = Column(String(100), default="pending")  # pending / success / failed
    error_message = Column(String(200), nullable=True)

    cae = Column(String(300), nullable=True)
    cae_due_date = Column(Date, nullable=True)

    invoice_date = Column(Date, nullable=True)

    pdf_url = Column(String(300), nullable=True)
    
    raw_afip_response = Column(JSON)
    fiscal_snapshot = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
