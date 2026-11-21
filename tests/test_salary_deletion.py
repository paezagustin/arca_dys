"""Baja lógica de sueldos: conservación, concurrencia y conciliación de reportes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.main import app
from app.models.registers import SalaryPayment
from app.services.business import save_entry
from app.services.metrics import period_metrics, year_metrics
from app.services.registers import delete_salary, save_register
from tests.test_business import values
from tests.test_closing_registers import register
from tests.test_migrations import migrate, scratch_database
from tests.test_simple_business import csrf


def create_salary(**changes):
    payload = register(**changes)
    with Session(engine) as db:
        identifier = save_register(db, SalaryPayment, payload).id
    return identifier, payload


def test_delete_preserves_original_and_replay_cannot_reactivate():
    identifier, payload = create_salary(amount="1250", employee="Juan Cruz")
    with Session(engine) as db:
        row = db.get(SalaryPayment, identifier)
        original = {column.name: getattr(row, column.name) for column in row.__table__.columns
                    if column.name not in {"version", "deleted_at"}}
        for version in (None, "bad", "0", "2"):
            with pytest.raises(ValueError):
                delete_salary(db, identifier, version)
            db.rollback()
        deleted = delete_salary(db, identifier, "1")
        timestamp = deleted.deleted_at
        assert timestamp is not None and timestamp.tzinfo is not None and deleted.version == 2
        assert delete_salary(db, identifier, "1").deleted_at == timestamp
        assert deleted.version == 2
        assert {key: getattr(deleted, key) for key in original} == original
        with pytest.raises(ValueError, match="eliminado"):
            save_register(db, SalaryPayment, payload)
        db.rollback()
        with pytest.raises(ValueError, match="no encontrado"):
            save_register(db, SalaryPayment, dict(payload, version="2"), identifier)
        db.rollback()
        assert save_register(db, SalaryPayment, dict(payload, entry_key=str(uuid4()))).id != identifier
        with pytest.raises(LookupError):
            delete_salary(db, 999999, "1")


def test_guest_delete_requires_csrf_and_version_and_is_only_on_edit():
    identifier, payload = create_salary(amount="1250")
    url = f"/salaries/{identifier}/delete"
    with TestClient(app) as guest:
        listing = guest.get("/salaries?fecha_desde=2026-01-01&fecha_hasta=2026-01-31")
        assert url not in listing.text
        edit = guest.get(f"/salaries?edit={identifier}")
        assert url in edit.text and ">Guardar</button>" in edit.text and "Guardar cambios" not in edit.text
        token = csrf(edit)
        assert guest.get(url).status_code == 405
        assert guest.post(url, data={"version": "1"}).status_code == 403
        assert guest.post(url, data={"csrf_token": token}).status_code == 422
        assert guest.post(url, data={"version": "9", "csrf_token": token}).status_code == 422
        query = "?edit=999&employee=Francisco&fecha_desde=2026-01-01&fecha_hasta=2026-01-31&page=1&redirect=https://example.com"
        response = guest.post(url + query, data={"version": "1", "csrf_token": token}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/salaries?employee=Francisco&fecha_desde=2026-01-01&fecha_hasta=2026-01-31&page=1&deleted=1"
        assert guest.post(url, data={"version": "1", "csrf_token": token}).status_code == 200
        assert guest.get(f"/salaries?edit={identifier}").status_code == 404
        assert guest.post("/salaries", data=dict(payload, id=identifier, version="2", csrf_token=token)).status_code == 404
        assert guest.post("/salaries", data=dict(payload, csrf_token=token)).status_code == 422
        assert guest.post("/salaries/999999/delete", data={"version": "1", "csrf_token": token}).status_code == 404
        listing = guest.get("/salaries?fecha_desde=2026-01-01&fecha_hasta=2026-01-31")
        assert "$ 1.250" not in listing.text and "0 registros" in listing.text


def test_deleted_salary_is_excluded_from_metrics_and_excel(client):
    removed, _ = create_salary(amount="1000", employee="Francisco", entry_date="2026-01-15")
    create_salary(amount="2000", employee="Juan Cruz", entry_date="2026-01-16")
    create_salary(amount="300", entry_date="2025-12-31")
    with Session(engine) as db:
        save_entry(db, values(entry_date="2026-01-15", cash_amount="10000", mp_amount="0"), "test")
        assert period_metrics(db, date(2026, 1, 1), date(2026, 1, 31))["result"] == Decimal("7000")
        delete_salary(db, removed, "1")
        period = period_metrics(db, date(2026, 1, 1), date(2026, 1, 31))
        january = year_metrics(db, 2026)[0]
        for report in (period, january):
            assert report["salary"] == Decimal("2000") and report["salary_count"] == 1
            assert report["employees"] == {"Francisco": None, "Juan Cruz": Decimal("2000")}
            assert report["result"] == Decimal("8000")
        assert db.get(SalaryPayment, removed).amount == Decimal("1000")
        assert db.scalar(text("SELECT count(*) FROM payments")) == 0
        assert db.scalar(text("SELECT count(*) FROM invoices")) == 0
    response = client.get("/dashboard/export?year=2026&month=1")
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content), data_only=True)
    rows = list(workbook["Sueldos"].iter_rows(min_row=2, values_only=True))
    assert len(rows) == 1 and rows[0][1:3] == ("Juan Cruz", 2000)


def test_pagination_total_and_employee_filter_share_deletion_condition(client):
    with Session(engine) as db:
        entries = [SalaryPayment(entry_key=str(uuid4()), entry_date=date(2026, 1, 10),
                   employee="Juan Cruz", amount=Decimal("1"), medium="efectivo", version=1) for _ in range(27)]
        db.add_all(entries)
        db.commit()
        for row in entries[:2]:
            delete_salary(db, row.id, "1")
    create_salary(employee="Francisco", amount="500")
    page = client.get("/salaries?employee=Juan+Cruz&fecha_desde=2026-01-01&fecha_hasta=2026-01-31")
    assert page.status_code == 200 and "Página 1 de 1 · 25 registros" in page.text
    assert "$ 25" in page.text and "$ 500" not in page.text


def test_concurrent_edit_and_delete_cannot_lose_correction():
    identifier, payload = create_salary(amount="100")

    def change(action):
        with Session(engine) as db:
            try:
                if action == "delete":
                    delete_salary(db, identifier, "1")
                else:
                    save_register(db, SalaryPayment, dict(payload, amount="200", version="1"), identifier)
                return "ok"
            except ValueError:
                db.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, ("edit", "delete"))) == ["conflict", "ok"]
    with Session(engine) as db:
        row = db.get(SalaryPayment, identifier)
        assert row.version == 2
        assert (row.amount, row.deleted_at is not None) in ((Decimal("100"), True), (Decimal("200"), False))


def test_migration_preserves_salary_and_refuses_to_reactivate_deleted(scratch_database):
    migrate(scratch_database, "0020_credit_person_names")
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO salary_payments(entry_key,entry_date,employee,amount,medium,version)
            VALUES ('SIM-SALARY-ORIGINAL','2026-01-10','Juan Cruz',123.45,'efectivo',7)"""))
        before = dict(db.execute(text("SELECT * FROM salary_payments")).mappings().one())
        sequence = db.execute(text("SELECT last_value,is_called FROM salary_payments_id_seq")).one()
    migrate(scratch_database, "0021_salary_deletion")
    with scratch_database.connect() as db:
        after = dict(db.execute(text("SELECT * FROM salary_payments")).mappings().one())
        assert after.pop("deleted_at") is None and after == before
        assert db.execute(text("SELECT last_value,is_called FROM salary_payments_id_seq")).one() == sequence
    migrate(scratch_database, "0020_credit_person_names", downgrade=True)
    migrate(scratch_database, "0021_salary_deletion")
    with scratch_database.begin() as db:
        db.execute(text("UPDATE salary_payments SET deleted_at=now()"))
    with pytest.raises(RuntimeError, match="reactivaría pagos de sueldos eliminados"):
        migrate(scratch_database, "0020_credit_person_names", downgrade=True)
    with scratch_database.connect() as db:
        assert db.scalar(text("SELECT deleted_at IS NOT NULL FROM salary_payments")) is True
