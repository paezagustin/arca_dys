from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Index, UniqueConstraint
from app.core.database import Base
from app.models.billing import utcnow


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(String(36), primary_key=True)
    dataset = Column(String(80), nullable=False)
    file_hash = Column(String(64), nullable=False)
    filename = Column(String(200), nullable=False)
    state = Column(String(20), nullable=False)
    report = Column(JSON, nullable=False)
    actor = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    confirmed_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("dataset", "file_hash", name="uq_import_file"),)


class ImportRow(Base):
    __tablename__ = "import_rows"
    id = Column(Integer, primary_key=True)
    batch_id = Column(String(36), ForeignKey("import_batches.id"), nullable=False)
    sheet = Column(String(80), nullable=False)
    row_number = Column(Integer, nullable=False)
    slot = Column(String(20), nullable=False)
    source_key = Column(String(64), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    kind = Column(String(20), nullable=False)
    raw = Column(JSON, nullable=False)
    proposed = Column(JSON, nullable=False)
    state = Column(String(20), nullable=False)
    issue = Column(String(500))
    resolution = Column(JSON)
    entry_id = Column(Integer, ForeignKey("business_entries.id"))
    __table_args__ = (UniqueConstraint("batch_id", "sheet", "row_number", "slot", name="uq_import_row"),
        Index("ix_import_rows_batch", "batch_id", "state", "id"), Index("ix_import_rows_source", "source_key"))


class ImportSupplierMap(Base):
    __tablename__ = "import_supplier_maps"
    batch_id = Column(String(36), ForeignKey("import_batches.id"), primary_key=True)
    label = Column(String(200), primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    actor = Column(String(80), nullable=False)
