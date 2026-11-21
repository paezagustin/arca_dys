"""Cuenta por persona, movimientos vigentes y evidencia inmutable de correcciones."""
from sqlalchemy import (Column, Integer, String, Text, Date, DateTime, Numeric, ForeignKey,
                        ForeignKeyConstraint, CheckConstraint, UniqueConstraint, Index, func)
from app.core.database import Base
from sqlalchemy.dialects.postgresql import JSONB


class CreditCustomer(Base):
    __tablename__ = "credit_customers"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_credit_customer_name"),
        CheckConstraint("phone = '' OR phone ~ '^[1-9][0-9]{9}$'", name="ck_credit_customer_phone"),
        CheckConstraint("version > 0 AND last_seq >= 0", name="ck_credit_customer_version"),)
    id = Column(Integer, primary_key=True)
    entry_key = Column(String(36), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    alias = Column(String(80), nullable=False, default="", server_default="")
    phone = Column(String(15), nullable=False, default="", server_default="")
    search_text = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    last_seq = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreditMovement(Base):
    __tablename__ = "credit_movements"
    __table_args__ = (
        UniqueConstraint("customer_id", "account_seq", name="uq_credit_movement_sequence"),
        UniqueConstraint("id", "customer_id", name="uq_credit_movement_owner"),
        ForeignKeyConstraint(["reversal_of", "customer_id"], ["credit_movements.id", "credit_movements.customer_id"],
                             name="fk_credit_reversal_owner", ondelete="RESTRICT"),
        CheckConstraint("delta <> 0 AND delta = trunc(delta) AND abs(delta) < 10000000000000000", name="ck_credit_movement_integer"),
        CheckConstraint("account_seq > 0", name="ck_credit_movement_sequence"),
        CheckConstraint("(kind IN ('purchase','opening') AND delta > 0 AND reversal_of IS NULL) OR "
                        "(kind = 'payment' AND delta < 0 AND reversal_of IS NULL) OR "
                        "(kind = 'reversal' AND reversal_of IS NOT NULL AND reversal_of <> id)",
                        name="ck_credit_movement_kind"),
        Index("ix_credit_movement_date", "customer_id", "entry_date", "id"),)
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("credit_customers.id", ondelete="RESTRICT"), nullable=False)
    account_seq = Column(Integer, nullable=False)
    entry_key = Column(String(36), nullable=False, unique=True)
    payload_hash = Column(String(64), nullable=False)
    kind = Column(String(12), nullable=False)
    delta = Column(Numeric(), nullable=False)
    entry_date = Column(Date, nullable=False)
    observation = Column(Text, nullable=False, default="", server_default="")
    reversal_of = Column(Integer, unique=True)
    actor = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    version = Column(Integer, nullable=False, server_default="1", default=1)
    deleted_at = Column(DateTime(timezone=True))
    change_key = Column(String(36))
    change_hash = Column(String(64))
    changed_by = Column(String(80))


class CreditMovementChange(Base):
    __tablename__ = "credit_movement_changes"
    id = Column(Integer, primary_key=True)
    movement_id = Column(Integer, ForeignKey("credit_movements.id", ondelete="RESTRICT"), nullable=False)
    entry_key = Column(String(36), nullable=False, unique=True)
    payload_hash = Column(String(64), nullable=False)
    before = Column(JSONB, nullable=False)
    after = Column(JSONB, nullable=False)
    actor = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CreditLegacyLink(Base):
    __tablename__ = "credit_legacy_links"
    __table_args__ = (ForeignKeyConstraint(["opening_movement_id", "customer_id"],
        ["credit_movements.id", "credit_movements.customer_id"], name="fk_credit_legacy_owner", ondelete="RESTRICT"),)
    legacy_credit_id = Column(Integer, ForeignKey("customer_credits.id", ondelete="RESTRICT"), primary_key=True)
    entry_key = Column(String(36), nullable=False, unique=True)
    payload_hash = Column(String(64), nullable=False)
    customer_id = Column(Integer, ForeignKey("credit_customers.id", ondelete="RESTRICT"), nullable=False)
    opening_movement_id = Column(Integer, unique=True)
    source_hash = Column(String(64), nullable=False)
    actor = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
