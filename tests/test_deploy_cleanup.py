"""La limpieza manual se ensaya solo en la DB descartable protegida por conftest."""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text, func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.payment_invoice import PaymentInvoice
from app.models.billing import BillingRequest, BillingReservation
from app.models.mp_event import MPEvent, PaymentChange
from app.models.settings import BusinessSettings, User
from app.models.business import BusinessEntry, Supplier
from app.models.data_import import DataImport, LegacyImportRow, LegacyImportSupplierMap
from app.models.registers import SalaryPayment, CustomerCredit

SCRIPT = Path("scripts/reset-business-data.sql").read_text(encoding="utf-8")
CLEANED = {"import_rows", "import_supplier_maps", "import_batches", "business_entries", "suppliers", "salary_payments", "customer_credits"}


def seed():
    with Session(engine) as db:
        payment = Payment(id_payment_mp="SIM-FACTURADO", status="approved", mont=Decimal("1234.56"), registered_arca=True)
        pending = Payment(id_payment_mp="SIM-POR-VERIFICAR", status="approved", mont=Decimal("2000"), registered_arca=False)
        invoice = Invoice(invoice_number="SIM-10-123", total_amount=Decimal("1234.56"), cae="SIM-CAE", raw_afip_response={"simulation": True})
        supplier = Supplier(name="Proveedor ficticio", name_key="proveedor ficticio")
        receipt = DataImport(id="receipt-test", dataset="initial-business-json-v1", file_hash="a"*64,
            filename="Datos ficticios", state="confirmed", report={}, actor="test")
        event = MPEvent(id="event-test", dedup_key="b"*64, topic="payment", resource="SIM-FACTURADO", payload={}, state="processed")
        db.add_all([payment, pending, invoice, supplier, receipt, event,
            BusinessSettings(id=1, values={"name": "Emisor ficticio", "point": 10}, version=2),
            User(username="administracion", password_hash="SIM-HASH", role="admin")])
        db.flush()
        request = BillingRequest(id="request-test", idempotency_key="SIM-REQUEST", state="uncertain", total=Decimal("2000"),
            invoice_date=date(2026, 1, 1), point=10, voucher_type=11, voucher_number=124, payment_ids=[pending.id],
            payment_snapshot=[{"id": pending.id}], fiscal_snapshot={"simulation": True}, payload={"CbteDesde": 124})
        entry = BusinessEntry(entry_key="entry-test", kind="expense", entry_date=date(2026, 1, 1), amount=Decimal("12.34"),
            expense_type="white", supplier_id=supplier.id)
        db.add_all([request, entry])
        db.flush()
        db.add_all([PaymentInvoice(payment_id=payment.id, invoice_id=invoice.id),
            BillingReservation(payment_id=pending.id, request_id=request.id),
            PaymentChange(payment_id=payment.id, event_id=event.id, previous_status="pending", new_status="approved", provider_updated_at=datetime(2026,1,1,tzinfo=timezone.utc)),
            LegacyImportRow(batch_id=receipt.id, sheet="Test", row_number=1, slot="D", source_key="c"*64, fingerprint="d"*64,
                kind="expense", raw={}, proposed={}, state="imported", entry_id=entry.id),
            LegacyImportSupplierMap(batch_id=receipt.id, label="Original ficticio", supplier_id=supplier.id, actor="test"),
            SalaryPayment(entry_key="salary-test", entry_date=date(2026,1,1), employee="Francisco", amount=Decimal("10"), medium="mercado pago"),
            CustomerCredit(entry_key="credit-test", customer="Cliente ficticio", amount=Decimal("5"), entry_date=date(2026,1,1), paid=False)])
        db.commit()


def protected_snapshot():
    with engine.connect() as db:
        rows = {name: list(db.execute(select(table).order_by(*table.primary_key.columns)).mappings())
            for name, table in Base.metadata.tables.items() if name not in CLEANED}
        rows["alembic_version"] = db.execute(text("SELECT version_num FROM alembic_version")).all()
        rows["fiscal_sequences"] = [db.scalar(text(f"SELECT last_value FROM {name}_id_seq")) for name in ("payments", "invoices", "payment_invoice")]
        return rows


def test_manual_cleanup_removes_only_management_and_preserves_all_fiscal_control():
    seed()
    before = protected_snapshot()
    with engine.begin() as db:
        db.exec_driver_sql(SCRIPT)
    assert protected_snapshot() == before
    with engine.connect() as db:
        assert all(db.scalar(select(func.count()).select_from(Base.metadata.tables[name])) == 0 for name in CLEANED)
        assert db.scalar(select(Payment.registered_arca).where(Payment.id_payment_mp == "SIM-FACTURADO")) is True
        assert db.scalar(select(BillingRequest.state)) == "uncertain"
        assert db.scalar(text("SELECT nextval('suppliers_id_seq')")) == 1
    # Repetirla mantiene intactas facturas, ID MP, reservas y configuración.
    with engine.begin() as db:
        db.exec_driver_sql(SCRIPT)
    assert protected_snapshot() == before


def test_manual_cleanup_rejects_wrong_schema_without_deleting_data():
    seed()
    try:
        with engine.begin() as db:
            db.execute(text("UPDATE alembic_version SET version_num='stale'"))
        with pytest.raises(DBAPIError, match="0013_mp_identity"):
            with engine.begin() as db:
                db.exec_driver_sql(SCRIPT)
        with engine.connect() as db:
            assert db.scalar(select(func.count()).select_from(BusinessEntry)) == 1
            assert db.scalar(select(func.count()).select_from(Supplier)) == 1
    finally:
        with engine.begin() as db:
            db.execute(text("UPDATE alembic_version SET version_num='0013_mp_identity'"))


def test_unexpected_foreign_key_blocks_cleanup_instead_of_cascading():
    seed()
    before = protected_snapshot()
    try:
        with engine.begin() as db:
            db.execute(text("CREATE TABLE test_reset_reference (supplier_id INTEGER REFERENCES suppliers(id))"))
            db.execute(text("INSERT INTO test_reset_reference SELECT id FROM suppliers"))
        with pytest.raises(DBAPIError):
            with engine.begin() as db:
                db.exec_driver_sql(SCRIPT)
        assert protected_snapshot() == before
        with engine.connect() as db:
            assert db.scalar(select(func.count()).select_from(BusinessEntry)) == 1
            assert db.scalar(select(func.count()).select_from(Supplier)) == 1
            assert db.scalar(select(func.count()).select_from(DataImport)) == 1
    finally:
        with engine.begin() as db:
            db.execute(text("DROP TABLE IF EXISTS test_reset_reference"))
