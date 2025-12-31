from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, JSON
from datetime import datetime
from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    id_payment_mp = Column(String, unique=True, index=True, nullable=False)

    status = Column(String, nullable=False)
    status_detail = Column(String)

    mont = Column(Float)
    type_of_paid = Column(String)

    date_approved = Column(DateTime, nullable=True)

    bill = Column(Boolean, default=False)
    registered_arca = Column(Boolean, default=False)
    id_arca = Column(String, default="")

    raw_json = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
