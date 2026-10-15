from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Date, DateTime, Numeric, JSON, Text, ForeignKey, UniqueConstraint, Index
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class BillingRequest(Base):
    __tablename__ = "billing_requests"
    __table_args__ = (Index("ix_billing_state", "state", "created_at"), Index("ix_billing_date", "invoice_date", "created_at", "id"))
    id = Column(String(36), primary_key=True)
    idempotency_key = Column(String(100), unique=True, nullable=False)
    state = Column(String(20), nullable=False)
    total = Column(Numeric(18, 2), nullable=False)
    invoice_date = Column(Date, nullable=False)
    point = Column(Integer, nullable=False)
    voucher_type = Column(Integer, nullable=False)
    voucher_number = Column(Integer)
    payment_ids = Column(JSON, nullable=False)
    payment_snapshot = Column(JSON, nullable=False)
    fiscal_snapshot = Column(JSON, nullable=False)
    payload = Column(JSON)
    response = Column(JSON)
    error = Column(Text)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class BillingReservation(Base):
    __tablename__ = "billing_reservations"
    payment_id = Column(Integer, ForeignKey("payments.id"), primary_key=True)
    request_id = Column(String(36), ForeignKey("billing_requests.id"), nullable=False)


class SimulatedVoucher(Base):
    """Proveedor ficticio persistente: permite recuperar respuestas tras un reinicio."""
    __tablename__ = "simulated_vouchers"
    __table_args__ = (UniqueConstraint("point", "voucher_type", "number", name="uq_simulated_voucher"),)
    id = Column(Integer, primary_key=True)
    point = Column(Integer, nullable=False)
    voucher_type = Column(Integer, nullable=False)
    number = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    response = Column(JSON, nullable=False)
