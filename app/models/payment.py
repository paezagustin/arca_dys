from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, JSON, Index
from datetime import datetime
from app.core.database import Base
from zoneinfo import ZoneInfo
def now_argentina():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_billing_date", "status", "registered_arca", "date_approved", "id"),
                      Index("ix_payments_status_date", "status", "date_approved"))

    id = Column(Integer, primary_key=True, index=True)

    id_payment_mp = Column(String(50), nullable=False, index=True)

    status = Column(String(50), nullable=False)
    status_detail = Column(String(150))

    mont = Column(Numeric(18, 2))
    type_of_paid = Column(String(50))

    date_approved = Column(DateTime, nullable=True)

    bill = Column(Boolean, default=False)
    registered_arca = Column(Boolean, default=False)

    raw_json = Column(JSON)
    provider_updated_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime, default=now_argentina)
