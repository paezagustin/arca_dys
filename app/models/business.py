"""Registro de gestión independiente de cobros y documentos fiscales."""
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, Numeric, JSON, ForeignKey, Index, CheckConstraint, text
from app.core.database import Base
from app.models.billing import utcnow


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    name_key = Column(String(150), nullable=False, unique=True)
    contact = Column(String(200), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)


class BusinessEntry(Base):
    __tablename__ = "business_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('sale','expense')", name="ck_business_kind"),
        CheckConstraint("amount >= 0 AND (kind = 'sale' OR amount > 0)", name="ck_business_amount"),
        CheckConstraint("expense_type IS NULL OR (kind='expense' AND expense_type IN ('white','black'))", name="ck_business_expense_type"),
        CheckConstraint("supplier_id IS NULL OR kind = 'expense'", name="ck_business_supplier"),
        Index("ix_business_date", "entry_date", "id"),
        Index("ix_business_kind_date", "kind", "active", "entry_date"),
        Index("ix_business_supplier_date", "supplier_id", "entry_date"),
        Index("uq_business_daily_sale", "entry_date", unique=True,
              postgresql_where=text("kind = 'sale' AND active")),
    )
    id = Column(Integer, primary_key=True)
    entry_key = Column(String(100), nullable=False, unique=True)
    kind = Column(String(10), nullable=False)
    entry_date = Column(Date, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    expense_type = Column(String(10))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    description = Column(Text, nullable=False, default="")
    origin = Column(String(20), nullable=False, default="manual")
    active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class MoneyMigrationAudit(Base):
    __tablename__ = "money_migration_audit"
    table_name = Column(String(40), primary_key=True)
    record_id = Column(Integer, primary_key=True)
    original_text = Column(String(100))
    converted = Column(Numeric(18, 2))
