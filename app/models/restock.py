"""Reposición de mercadería e historial de pedidos a proveedores."""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.billing import utcnow


class RestockProduct(Base):
    __tablename__ = "restock_products"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_restock_product_source"),
        CheckConstraint(
            "(source IS NULL AND external_id IS NULL AND catalog_status IS NULL) OR "
            "(source IS NOT NULL AND length(source) > 0 AND external_id IS NOT NULL AND length(external_id) > 0 "
            "AND catalog_status IS NOT NULL AND catalog_status IN ('active','inactive','missing'))",
            name="ck_restock_product_source",
        ),
        Index("ix_restock_product_name", "name_key", "id"),
        Index("ix_restock_product_barcode", "barcode"),
    )

    id = Column(Integer, primary_key=True)
    request_key = Column(String(36), unique=True)
    name = Column(String(180), nullable=False)
    name_key = Column(Text, nullable=False)
    search_text = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    presentation = Column(String(160), nullable=False, default="")
    barcode = Column(String(100), nullable=False, default="")
    active = Column(Boolean, nullable=False, default=True)
    source = Column(String(40))
    external_id = Column(String(160))
    catalog_status = Column(String(10))
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    suppliers = relationship("RestockProductSupplier", order_by="RestockProductSupplier.supplier_id")

    @property
    def available(self):
        return self.active and self.catalog_status in {None, "active"}


class RestockProductSupplier(Base):
    __tablename__ = "restock_product_suppliers"
    __table_args__ = (
        Index("ix_restock_products_by_supplier", "supplier_id", "product_id"),
        Index("uq_restock_preferred_supplier", "product_id", unique=True, postgresql_where=text("preferred")),
    )

    product_id = Column(ForeignKey("restock_products.id"), primary_key=True)
    supplier_id = Column(ForeignKey("suppliers.id"), primary_key=True)
    preferred = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    supplier = relationship("Supplier")


class RestockNeed(Base):
    __tablename__ = "restock_needs"
    __table_args__ = (
        CheckConstraint("status IN ('pending','ordered','received','cancelled')", name="ck_restock_need_status"),
        CheckConstraint("quantity > 0", name="ck_restock_need_quantity"),
        Index("uq_restock_active_need", "product_id", unique=True,
              postgresql_where=text("status IN ('pending','ordered')")),
        Index("ix_restock_need_status_date", "status", "created_at", "id"),
        Index("ix_restock_need_product", "product_id"),
    )

    id = Column(Integer, primary_key=True)
    request_key = Column(String(36), nullable=False, unique=True)
    product_id = Column(ForeignKey("restock_products.id"), nullable=False)
    status = Column(String(10), nullable=False, default="pending")
    quantity = Column(Numeric(12, 3))
    unit = Column(String(160), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    product = relationship("RestockProduct")


class SupplierOrder(Base):
    __tablename__ = "restock_orders"
    __table_args__ = (
        Index("ix_restock_order_date", "created_at", "id"),
        Index("ix_restock_order_supplier_date", "supplier_id", "created_at", "id"),
    )

    id = Column(Integer, primary_key=True)
    request_key = Column(String(36), nullable=False, unique=True)
    request_hash = Column(String(64), nullable=False)
    supplier_id = Column(ForeignKey("suppliers.id"), nullable=False)
    supplier_name = Column(String(150), nullable=False)
    notes = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    closed_at = Column(DateTime(timezone=True))
    lines = relationship("SupplierOrderLine", order_by="SupplierOrderLine.id", back_populates="order")


class SupplierOrderLine(Base):
    __tablename__ = "restock_order_lines"
    __table_args__ = (
        UniqueConstraint("order_id", "need_id", name="uq_restock_order_need"),
        CheckConstraint("quantity > 0", name="ck_restock_line_quantity"),
        CheckConstraint(
            "(outcome = 'waiting' AND resolved_at IS NULL) OR "
            "(outcome IN ('received','undelivered','cancelled') AND resolved_at IS NOT NULL)",
            name="ck_restock_line_resolution",
        ),
        Index("uq_restock_waiting_line", "need_id", unique=True, postgresql_where=text("outcome = 'waiting'")),
        Index("ix_restock_line_need", "need_id"),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(ForeignKey("restock_orders.id"), nullable=False)
    need_id = Column(ForeignKey("restock_needs.id"), nullable=False)
    product_name = Column(String(180), nullable=False)
    presentation = Column(String(160), nullable=False)
    barcode = Column(String(100), nullable=False)
    search_text = Column(Text, nullable=False)
    quantity = Column(Numeric(12, 3))
    unit = Column(String(160), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    outcome = Column(String(11), nullable=False, default="waiting")
    receipt_notes = Column(Text, nullable=False, default="")
    resolved_at = Column(DateTime(timezone=True))
    order = relationship("SupplierOrder", back_populates="lines")


class RestockCatalogSync(Base):
    __tablename__ = "restock_catalog_sync"

    source = Column(String(40), primary_key=True)
    last_attempt_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
