from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.business import BusinessEntry
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.mp_event import MPEvent
from app.services.business import save_entry, save_supplier
from app.services.metrics import year_metrics, period_total, change, bounds
from app.services.excel_import import prepare_import, confirm_import
from app.services.excel_reader import read_excel
from tests.test_business import values
from tests.test_excel_import import workbook_bytes


def test_metrics_reconcile_registered_detail_and_keep_mp_and_invoices_separate(client):
    with Session(engine) as db:
        for data in [values(entry_date="2026-01-01", amount="100.10"), values(entry_date="2026-01-02", amount="0"),
            values(kind="expense", amount="5.05", expense_type="black"),
            values(kind="expense", amount="25.05", category="Mercadería"),
            values(entry_date="2026-02-01", amount="200.20"),
            values(entry_date="2026-02-01", kind="expense", amount="50.20", category="Servicio"),
            values(entry_date="2025-12-01", amount="50")]:
            save_entry(db, data, "test")
        db.add_all([Payment(id_payment_mp="SIM-APPROVED", status="approved", mont=Decimal("9999"), date_approved=datetime(2026,1,1)),
            Payment(id_payment_mp="SIM-REFUNDED", status="refunded", mont=Decimal("8888"), date_approved=datetime(2026,1,1)),
            Invoice(invoice_number="SIM-METRICS", total_amount=Decimal("3000"), cae="SIM-CAE", invoice_date=date(2026,1,1)),
            Invoice(invoice_number="SIM-FAILED", total_amount=Decimal("5000"), status="failed", invoice_date=date(2026,1,1))])
        db.commit()
        rows = year_metrics(db, 2026)
        january, february, march = rows[:3]
        assert january["sale"] == Decimal("100.10") and january["days"] == 2
        assert january["average"] == Decimal("50.05") and january["min_sale"] == 0
        assert january["result"] == Decimal("70.00")
        assert january["mp"] == Decimal(9999) and january["invoices"] == Decimal(3000)
        assert february["result"] == Decimal(150) and march["result"] is None
        assert march["sale"] is None and march["days"] == 0
        total = period_total(rows)
        assert total["result"] == Decimal("220.00") and total["average"] == Decimal("100.10")
    page = client.get("/dashboard?year=2026&month=1")
    assert page.status_code == 200 and "$ 70,00" in page.text and "$ 9.999,00" in page.text
    assert "$ 50,10" in page.text and "Diciembre 2025" in page.text
    assert '<svg ' in page.text and 'aria-labelledby="chart-title chart-description"' in page.text
    assert "Ganancia" in page.text and "Otros ingresos" not in page.text
    assert "saldo pendiente" not in page.text.lower() and "pendientes de facturar" not in page.text.lower()


def test_import_and_dashboard_aggregate_same_values_without_historical_double_counting():
    content = workbook_bytes()
    with Session(engine) as db:
        batch = prepare_import(db, content, "Libro-qa", "ejemplo.xlsx", "test", read_excel(content, "Libro-qa"))
        confirm_import(db, batch.id, "test")
        january = year_metrics(db, 2026)[0]
        assert january["sale"] == Decimal(110) and january["expense"] == Decimal(120)
        assert january["result"] == Decimal(-10) and january["days"] == 3
        assert year_metrics(db, 2022)[0]["result"] is None


def test_grouped_supplier_and_expense_type_lists_have_independent_sql_pagination(client):
    with Session(engine) as db:
        for n in range(27):
            supplier = save_supplier(db, {"name": f"Ficticio {n:02}"}, "test")
            save_entry(db, values(kind="expense", amount="1.25", category=f"Categoría {n:02}", supplier_id=str(supplier.id)), "test")
    page = client.get("/dashboard?year=2026&month=1&suppliers_page=2&categories_page=1")
    assert page.status_code == 200
    assert "Página 2 de 2" in page.text and "Página 1 de 1" in page.text
    assert "Ficticio 26" in page.text and "$ 33,75" in page.text
    assert "&lt;built-in" not in page.text


def test_leap_day_and_timestamp_boundaries():
    with Session(engine) as db:
        save_entry(db, values(entry_date="2024-02-29", amount="1.01"), "test")
        db.add_all([Payment(id_payment_mp="SIM-END", status="approved", mont=Decimal("2.02"), date_approved=datetime(2024,12,31,23,59,59,999999)),
            Payment(id_payment_mp="SIM-NEXT", status="approved", mont=Decimal("3.03"), date_approved=datetime(2025,1,1))])
        db.commit()
        rows = year_metrics(db, 2024)
        assert rows[1]["sale"] == Decimal("1.01")
        assert rows[11]["mp"] == Decimal("2.02")
    assert bounds(2024, 2)[1] == date(2024,2,29)
    assert change(Decimal(1), Decimal(0))["percent"] is None


@pytest.mark.parametrize("query", ["year=0", "year=10000", "month=13", "month=-1", "year=no"])
def test_bad_periods_show_clear_error(client, query):
    response = client.get("/dashboard?" + query, headers={"Accept": "text/html"})
    assert response.status_code == 422 and "Revisá" in response.text


def test_request_size_limit_checks_declared_and_streamed_bytes(client):
    assert client.post("/business/imports", content=b"x", headers={"content-length": str(7*1024*1024)}).status_code == 413
    assert client.post("/mp/webhook", content=(b"x"*65536 for _ in range(5))).status_code == 413
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(MPEvent)) == 0


def test_large_fiscal_amount_never_loses_cents_even_with_raised_admin_limit(client):
    from app.services.settings import read_settings, save_settings
    from app.models.billing import BillingRequest
    from app.models.settings import BillingPreview
    with Session(engine) as db:
        settings, version = read_settings(db)
        settings["maximum"] = "9999999999999999.99"
        save_settings(db, settings, version, "admin")
    response = client.post("/ARCA/invoice/manual/preview", data={"amount": "1000000000000000.01"})
    assert response.status_code == 422 and "precisión" in response.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(BillingRequest)) == 0
        assert db.scalar(select(func.count()).select_from(BillingPreview)) == 0
