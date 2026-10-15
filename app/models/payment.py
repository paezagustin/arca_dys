from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, JSON
from datetime import datetime
from app.core.database import Base
from zoneinfo import ZoneInfo
def now_argentina():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    id_payment_mp = Column(String(50), nullable=False, index=True)

    status = Column(String(50), nullable=False)
    status_detail = Column(String(150))

    mont = Column(Float)
    type_of_paid = Column(String(50))

    date_approved = Column(DateTime, nullable=True)

    bill = Column(Boolean, default=False)
    registered_arca = Column(Boolean, default=False)

    raw_json = Column(JSON)

    created_at = Column(DateTime, default=now_argentina)
