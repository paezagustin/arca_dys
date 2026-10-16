from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.registers import CustomerCredit
from app.services.registers import save_register
from tests.test_closing_registers import register
from tests.test_migrations import scratch_database, migrate


def test_quick_payment_sets_date_once_and_replay_preserves_it(client, monkeypatch):
    with Session(engine) as db:
        identifier = save_register(db, CustomerCredit, register()).id
    monkeypatch.setattr("app.api.registers.business_today", lambda: date(2026, 10, 16))
    assert client.post(f"/fiados/{identifier}/paid", data={"version": "1"}).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid is True and row.paid_date == date(2026, 10, 16) and row.version == 2
    monkeypatch.setattr("app.api.registers.business_today", lambda: date(2026, 10, 17))
    assert client.post(f"/fiados/{identifier}/paid", data={"version": "1"}).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid_date == date(2026, 10, 16) and row.version == 2
    page = client.get("/fiados?paid=yes")
    assert "Fecha de pago" in page.text and "16/10/2026" in page.text


def test_form_paid_date_survives_edits_and_replay_and_clears_when_reopened(client, monkeypatch):
    monkeypatch.setattr("app.services.registers.business_today", lambda: date(2026, 10, 16))
    data = register(paid="1", paid_date="1900-01-01")
    assert client.post("/fiados", data=data).status_code == 200
    monkeypatch.setattr("app.services.registers.business_today", lambda: date(2026, 10, 17))
    assert client.post("/fiados", data=data).status_code == 200
    with Session(engine) as db:
        row = db.scalar(select(CustomerCredit))
        identifier = row.id
        assert row.paid_date == date(2026, 10, 16)
    edited = dict(data, id=str(identifier), version="1", observation="Corregida")
    assert client.post("/fiados", data=edited).status_code == 200
    with Session(engine) as db:
        assert db.get(CustomerCredit, identifier).paid_date == date(2026, 10, 16)
    assert client.post("/fiados", data=dict(edited, paid="0", version="2")).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid is False and row.paid_date is None
    assert client.post("/fiados", data=dict(edited, paid="1", version="3")).status_code == 200
    with Session(engine) as db:
        assert db.get(CustomerCredit, identifier).paid_date == date(2026, 10, 17)


def test_legacy_paid_record_stays_without_invented_date_on_edit_or_repeated_mark(client):
    with Session(engine) as db:
        row = CustomerCredit(entry_key="SIM-LEGACY-PAID", entry_date=date(2020, 1, 1),
            amount=Decimal("10.25"), customer="Cliente ficticio anterior", observation="", paid=True, version=1)
        db.add(row)
        db.commit()
        identifier = row.id
    assert client.post(f"/fiados/{identifier}/paid", data={"version": "1"}).status_code == 200
    assert client.post("/fiados", data=register(id=str(identifier), version="1", paid="1")).status_code == 200
    with Session(engine) as db:
        assert db.get(CustomerCredit, identifier).paid_date is None


def test_migration_preserves_credits_and_requires_unpaid_dates_to_be_empty(scratch_database):
    migrate(scratch_database, "0011_sales_payroll_credits")
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO customer_credits(entry_key,customer,amount,observation,entry_date,paid,version)
            VALUES ('SIM-PAID','Cliente ficticio A',123.45,'','2026-01-01',true,1),
                   ('SIM-OPEN','Cliente ficticio B',67.89,'','2026-01-02',false,1)"""))
    migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT amount,paid,paid_date FROM customer_credits ORDER BY id")).all() == [
            (Decimal("123.45"),True,None), (Decimal("67.89"),False,None)]
    with pytest.raises(IntegrityError), scratch_database.begin() as db:
        db.execute(text("UPDATE customer_credits SET paid_date='2026-10-16' WHERE paid=false"))
