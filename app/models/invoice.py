from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON
from datetime import datetime
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)

    invoice_number = Column(String, unique=True, nullable=False)
    total_amount = Column(Float, nullable=False)

    status = Column(String, default="pending")  #pending / success / failed
    error_message = Column(String, nullable=True)

    cae = Column(String, nullable=True)
    cae_due_date = Column(Date, nullable=True)

    invoice_date = Column(Date, nullable=False)

    pdf_url = Column(String, nullable=True)
    
    raw_afip_response = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
