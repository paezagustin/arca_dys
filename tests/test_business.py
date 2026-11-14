from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4
import re
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import engine
from app.models.business import BusinessEntry, Supplier
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.services.business import save_entry, save_supplier, money
from tests.test_migrations import scratch_database, migrate


def values(**changes):
    data = dict({"entry_key": str(uuid4()), "kind": "sale", "entry_date": "2026-01-10", "amount": "1500",
        "expense_type": "white"}, **changes)
    if data["kind"] == "sale":
        data.setdefault("cash_amount", data["amount"])
        data.setdefault("mp_amount", "0")
    return data


def test_sales_are_independent_idempotent_and_other_income_is_rejected(client, monkeypatch):
    monkeypatch.setattr("app.api.business.business_today", lambda: date(2026, 2, 1))
    data = values()
    page = client.post("/business/entries/new", data=data)
    assert page.status_code == 200
    assert page.url.params["fecha_desde"] == page.url.params["fecha_hasta"] == data["entry_date"]
    assert client.post("/business/entries/new", data=data).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(BusinessEntry)) == 1
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
        with pytest.raises(ValueError):
            save_entry(db, values(kind="income", amount="50.20"), "admin")
    assert "$ 1.500" in page.text and "Otro ingreso" not in page.text


def test_daily_sale_unique_under_concurrency():
    def save(_):
        with Session(engine) as db:
            try:
                save_entry(db, values(), "test")
                return "saved"
            except IntegrityError:
                db.rollback()
                return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["conflict", "saved"]


def test_edit_without_reason_preserves_version_protection_and_has_no_history(client):
    with Session(engine) as db:
        identifier = save_entry(db, values(), "admin").id
    data = values(version="1", amount="2000")
    assert client.post(f"/business/entries/{identifier}", data=data, follow_redirects=False).status_code == 303
    assert client.post(f"/business/entries/{identifier}", data=data).status_code == 422
    with Session(engine) as db:
        row = db.get(BusinessEntry, identifier)
        assert row.amount == Decimal("2000") and row.version == 2
    page = client.get(f"/business/entries/{identifier}")
    assert "Historial de cambios" not in page.text and 'name="reason"' not in page.text
    assert 'name="medium"' not in page.text and 'name="active"' not in page.text
    assert 'name="kind" value="sale"' in page.text


def test_supplier_selection_archival_and_no_silent_duplicate(client):
    assert client.post("/business/suppliers/new", data={"name": "Proveedor Ficticio", "contact": "ejemplo"}, follow_redirects=False).status_code == 303
    assert client.post("/business/suppliers/new", data={"name": " proveedor  ficticio "}).status_code == 422
    with Session(engine) as db:
        supplier = db.scalar(select(Supplier))
        identifier = supplier.id
        save_entry(db, values(kind="expense", category="Mercadería", supplier_id=str(identifier)), "admin")
        save_supplier(db, {"name": supplier.name, "version": "1", "active": "0", "reason": "Dejar de usar"}, "admin", identifier)
        with pytest.raises(ValueError, match="activo"):
            save_entry(db, values(kind="expense", supplier_id=str(identifier), category="Compra"), "admin")
    page = client.get("/business")
    assert "Proveedor Ficticio" in page.text
    assert client.post("/business/entries/new", data=values(supplier_id=str(identifier))).status_code == 422


def test_supplier_bank_details_create_edit_clear_and_list(client):
    base = "/business/suppliers"
    data = {"name": "Proveedor Ficticio", "contact": "Contacto interno", "notes": "Nota de prueba",
            "cbu": "0012345678901234567890", "alias": "Cuenta-Prueba.01"}
    assert client.post(f"{base}/new", data=data, follow_redirects=False).status_code == 303
    assert client.post(f"{base}/new", data={"name": "Otro proveedor"}, follow_redirects=False).status_code == 303
    with Session(engine) as db:
        row = db.scalar(select(Supplier).where(Supplier.name == data["name"]))
        supplier_url = f"{base}/{row.id}"
        assert (row.cbu, row.alias, row.contact) == (data["cbu"], data["alias"], data["contact"])
        other = db.scalar(select(Supplier).where(Supplier.name == "Otro proveedor"))
        assert other.cbu is None and other.alias is None

    page = client.get(base, params={"q": "proveedor ficticio"})
    assert all(f"<th>{label}</th>" in page.text for label in ("Notas", "CBU", "Alias"))
    assert all(data[key] in page.text for key in ("notes", "cbu", "alias"))
    assert "Contacto" not in page.text and "Otro proveedor" not in page.text
    form = client.get(supplier_url)
    assert all(f'value="{data[key]}"' in form.text for key in ("cbu", "alias", "contact"))

    updated = dict(data, cbu="0000000000000000000001", alias="Otro.Alias", active="0", version="1")
    assert client.post(supplier_url, data=updated, follow_redirects=False).status_code == 303
    with Session(engine) as db:
        row = db.scalar(select(Supplier).where(Supplier.name == data["name"]))
        assert (row.cbu, row.alias) == (updated["cbu"], updated["alias"])
    assert "<td>Inactivo</td>" in client.get(base).text
    assert client.get(f"{base}/search", params={"q": data["name"]}).json() == []

    assert client.post(supplier_url, data=dict(updated, cbu=" ", alias="", version="2"),
                       follow_redirects=False).status_code == 303
    with Session(engine) as db:
        row = db.scalar(select(Supplier).where(Supplier.name == data["name"]))
        assert row.cbu is None and row.alias is None and row.contact == data["contact"]


@pytest.mark.parametrize(("field", "value"), [
    ("cbu", "0" * 21), ("cbu", "0" * 23), ("cbu", "０" * 22),
    ("alias", "corto"), ("alias", "a" * 21), ("alias", "alias_inválido"), ("alias", "alias invalido"),
])
def test_supplier_rejects_invalid_bank_details(client, field, value):
    response = client.post("/business/suppliers/new", data={"name": "Proveedor ficticio", field: value})
    assert response.status_code == 422
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Supplier)) == 0


def test_supplier_bank_migration_preserves_existing_data(scratch_database):
    migrate(scratch_database, "0014_credit_timestamps")
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO suppliers (id, name, name_key, contact, notes, active, version)
            VALUES (17, 'Proveedor histórico ficticio', 'proveedor histórico ficticio', 'Contacto ficticio',
                    'Nota anterior', false, 3)"""))
        db.execute(text("""INSERT INTO business_entries
            (entry_key, kind, entry_date, amount, expense_type, supplier_id, description, origin, active, version, created_at)
            VALUES ('test-history', 'expense', '2026-01-10', 1500, 'white', 17, '', 'manual', false, 2, now())"""))
        supplier_before = db.execute(text("SELECT to_jsonb(suppliers) FROM suppliers")).scalar_one()
        expense_before = db.execute(text("SELECT to_jsonb(business_entries) FROM business_entries")).scalar_one()
    migrate(scratch_database)
    with scratch_database.connect() as db:
        supplier_after = db.execute(text("SELECT to_jsonb(suppliers) FROM suppliers")).scalar_one()
        assert supplier_after == dict(supplier_before, cbu=None, alias=None)
        assert db.execute(text("SELECT to_jsonb(business_entries) FROM business_entries")).scalar_one() == expense_before


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "1.005", "10000000000000000", "", "1.000,00"])
def test_invalid_money_is_not_silently_rounded(amount):
    with pytest.raises(ValueError):
        money(amount)


def test_zero_is_distinct_from_blank(client):
    assert client.post("/business/entries/new", data=values(amount="0"), follow_redirects=False).status_code == 303
    with Session(engine) as db:
        identifier = db.scalar(select(BusinessEntry.id))
    assert 'value="0" placeholder="0"' in client.get(f"/business/entries/{identifier}").text
    assert 'name="expense_type"' in client.get("/business/entries/new?kind=expense").text
    assert client.post("/business/entries/new", data=values(kind="expense", amount="0", category="Compra")).status_code == 422
    assert client.post("/business/entries/new", data=values(entry_date="2026-02-30")).status_code == 422


def test_forms_escape_text_and_filters_are_paginated(client):
    with Session(engine) as db:
        for n in range(30):
            save_entry(db, values(kind="expense", category="Prueba", description="<script>alert(1)</script>", amount=str(n + 1)), "admin")
    page = client.get("/business?page=2&kind=expense")
    assert "Página 2 de 2" in page.text and "&lt;script&gt;" in page.text and "<script>alert" not in page.text
    assert client.get("/business?fecha_desde=2026-03-01&fecha_hasta=2026-01-01").status_code == 422


def test_numeric_migration_preserves_rows_and_original_representations(scratch_database):
    migrate(scratch_database, "0006_listings")
    with scratch_database.begin() as db:
        db.execute(text("INSERT INTO payments(id_payment_mp,status,mont) VALUES ('SIM-DECIMAL','approved',0.1 + 0.2), ('SIM-NULL','pending',NULL)"))
        db.execute(text("INSERT INTO invoices(total_amount) VALUES (12345.67)"))
    migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT mont FROM payments WHERE id_payment_mp='SIM-DECIMAL'")).scalar_one() == Decimal("0.30")
        assert db.execute(text("SELECT count(*) FROM money_migration_audit")).scalar_one() == 3
        assert db.execute(text("SELECT converted FROM money_migration_audit WHERE table_name='invoices'")).scalar_one() == Decimal("12345.67")
        assert db.execute(text("SELECT mont FROM payments WHERE id_payment_mp='SIM-NULL'")).scalar_one() is None


@pytest.mark.parametrize("amount", ["1.235", "'NaN'::float8", "'Infinity'::float8", "10000000000000000"])
def test_numeric_migration_refuses_unexpected_values_atomically(scratch_database, amount):
    migrate(scratch_database, "0006_listings")
    with scratch_database.begin() as db:
        db.execute(text(f"INSERT INTO payments(id_payment_mp,status,mont) VALUES ('SIM-INVALID','approved',{amount})"))
    with pytest.raises(RuntimeError, match="Conversión monetaria detenida"):
        migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0006_listings"
        assert db.execute(text("SELECT count(*) FROM payments")).scalar_one() == 1
