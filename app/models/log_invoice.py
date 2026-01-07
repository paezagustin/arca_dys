from sqlalchemy import Column, Integer, DateTime, String
from datetime import datetime
from app.core.database import Base


class LogInvoice(Base):
    __tablename__ = "logs_invoice"

    id = Column(Integer, primary_key=True, index=True)

    error = Column(String(300), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)