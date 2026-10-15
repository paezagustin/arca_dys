from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, ForeignKey, Index
from app.core.database import Base
from app.models.billing import utcnow


class MPEvent(Base):
    __tablename__ = "mp_events"
    __table_args__ = (Index("ix_mp_events_queue", "state", "next_attempt_at"),)
    id = Column(String(36), primary_key=True)
    dedup_key = Column(String(64), unique=True, nullable=False)
    topic = Column(String(50), nullable=False)
    resource = Column(String(200), nullable=False)
    payload = Column(JSON, nullable=False)
    state = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at = Column(DateTime(timezone=True))


class PaymentChange(Base):
    __tablename__ = "payment_changes"
    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    event_id = Column(String(36), ForeignKey("mp_events.id"), nullable=False)
    previous_status = Column(String(50))
    new_status = Column(String(50), nullable=False)
    provider_updated_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
