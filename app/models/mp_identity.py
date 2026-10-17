"""Identidad operativa separada del historial de filas MP."""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, String
from app.core.database import Base
from app.models.billing import utcnow


class MPPaymentIdentity(Base):
    __tablename__ = "mp_payment_identities"
    __table_args__ = (CheckConstraint(
        "(legacy_duplicate AND payment_id IS NULL) OR (NOT legacy_duplicate AND payment_id IS NOT NULL)",
        name="ck_mp_identity_mapping"),)
    id_payment_mp = Column(String(50), primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), unique=True)
    legacy_duplicate = Column(Boolean, nullable=False)


class MPLegacyPaymentSnapshot(Base):
    __tablename__ = "mp_legacy_payment_snapshots"
    payment_id = Column(Integer, ForeignKey("payments.id"), primary_key=True)
    snapshot = Column(JSON, nullable=False)


class MPLegacyTransition(Base):
    __tablename__ = "mp_legacy_transitions"
    id = Column(String(40), primary_key=True)
    source_revision = Column(String(32), nullable=False)
    target_revision = Column(String(32), nullable=False)
    report = Column(JSON, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
