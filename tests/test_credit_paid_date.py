from datetime import date, datetime, timezone
from decimal import Decimal
from html import unescape
import re
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.registers import CustomerCredit
from app.services.registers import save_register
from tests.test_closing_registers import register
from tests.test_migrations import scratch_database, migrate


def freeze_clock(monkeypatch, day, hour, minute):
    instant = datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.registers.utcnow", lambda: instant)
    return instant


def test_quick_payment_sets_date_once_and_replay_preserves_it(client, monkeypatch):
    created = freeze_clock(monkeypatch, 16, 12, 15)
    with Session(engine) as db:
        identifier = save_register(db, CustomerCredit, register(entry_date="2026-10-10")).id
    paid = freeze_clock(monkeypatch, 17, 2, 30)
    action = f"/fiados/{identifier}/paid"
    invalid = client.post(action, params={"fecha_desde": "2026-10-17", "fecha_hasta": "2026-10-16"},
                          data={"version": "1"})
    assert invalid.status_code == 422
    with Session(engine) as db:
        assert not db.get(CustomerCredit, identifier).paid
    response = client.post(action, data={"version": "1"})
    assert response.status_code == 200 and dict(response.url.params) == {"paid": "no", "stored": "1"}
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid is True and row.paid_date == date(2026, 10, 16) and row.version == 2
        assert row.created_at == created and row.paid_at == paid
    freeze_clock(monkeypatch, 17, 4, 0)
    assert client.post(f"/fiados/{identifier}/paid", data={"version": "1"}).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid_date == date(2026, 10, 16) and row.paid_at == paid and row.version == 2
    page = client.get("/fiados?paid=yes&fecha_desde=2026-10-10&fecha_hasta=2026-10-10")
    assert "10/10/2026<br><small>Registro 16/10/2026 09:15" in page.text
    assert "16/10/2026 23:30" in page.text


@pytest.mark.parametrize("paid", ["no", "all"])
def test_quick_payment_returns_to_unpaid_with_the_same_dates(client, monkeypatch, paid):
    with Session(engine) as db:
        identifier = save_register(db, CustomerCredit, register(
            entry_date="2026-10-10", customer="Fiado para pagar")).id
        save_register(db, CustomerCredit, register(entry_date="2026-10-11", customer="Pendiente en rango"))
        save_register(db, CustomerCredit, register(entry_date="2026-10-20", customer="Pendiente fuera del rango"))
    freeze_clock(monkeypatch, 16, 12, 0)
    dates = {"fecha_desde": "2026-10-09", "fecha_hasta": "2026-10-12"}
    page = client.get("/fiados", params={"paid": paid, **dates})
    action = re.search(rf'action="(/fiados/{identifier}/paid[^"]*)"', page.text).group(1)
    response = client.post(unescape(action), data={"version": "1"})
    assert response.status_code == 200
    assert dict(response.url.params) == {"paid": "no", "stored": "1", **dates}
    assert '<option value="no" selected>No</option>' in response.text
    assert "Pendiente en rango" in response.text
    assert "Fiado para pagar" not in response.text and "Pendiente fuera del rango" not in response.text
    paid_page = client.get("/fiados", params={"paid": "yes", **dates})
    assert "Fiado para pagar" in paid_page.text and "16/10/2026" in paid_page.text


def test_form_paid_date_survives_edits_and_replay_and_clears_when_reopened(client, monkeypatch):
    created = freeze_clock(monkeypatch, 16, 18, 45)
    data = register(paid="1", paid_date="1900-01-01", created_at="1900-01-01", paid_at="1900-01-01")
    assert client.post("/fiados", data=data).status_code == 200
    paid_again = freeze_clock(monkeypatch, 17, 12, 10)
    assert client.post("/fiados", data=data).status_code == 200
    with Session(engine) as db:
        row = db.scalar(select(CustomerCredit))
        identifier = row.id
        assert row.paid_date == date(2026, 10, 16)
        assert row.created_at == row.paid_at == created
    edited = dict(data, id=str(identifier), version="1", observation="Corregida")
    assert client.post("/fiados", data=edited).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid_date == date(2026, 10, 16) and row.paid_at == created
    assert client.post("/fiados", data=dict(edited, paid="0", version="2")).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid is False and row.paid_date is None and row.paid_at is None
    assert client.post("/fiados", data=dict(edited, paid="1", version="3")).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid_date == date(2026, 10, 17) and row.paid_at == paid_again
        assert row.created_at == created


@pytest.mark.parametrize("old_date", [None, date(2020, 1, 2)])
def test_legacy_paid_record_keeps_known_dates_without_inventing_times(client, old_date):
    with Session(engine) as db:
        row = CustomerCredit(entry_key="SIM-LEGACY-PAID", entry_date=date(2020, 1, 1),
            amount=Decimal("10.25"), customer="Cliente ficticio anterior", observation="", paid=True,
            paid_date=old_date, version=1)
        db.add(row)
        db.commit()
        identifier = row.id
    assert client.post(f"/fiados/{identifier}/paid", data={"version": "1"}).status_code == 200
    assert client.post("/fiados", data=register(id=str(identifier), version="1", paid="1")).status_code == 200
    with Session(engine) as db:
        row = db.get(CustomerCredit, identifier)
        assert row.paid_date == old_date and row.paid_at is None and row.created_at is None
    page = client.get("/fiados?paid=yes")
    assert "<small>Registro " not in page.text
    if old_date:
        assert "<td>02/01/2020</td>" in page.text


def test_migration_preserves_credits_and_requires_unpaid_dates_to_be_empty(scratch_database):
    migrate(scratch_database, "0011_sales_payroll_credits")
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO customer_credits(entry_key,customer,amount,observation,entry_date,paid,version)
            VALUES ('SIM-PAID','Cliente ficticio A',123.45,'','2026-01-01',true,1),
                   ('SIM-OPEN','Cliente ficticio B',67.89,'','2026-01-02',false,1)"""))
    migrate(scratch_database, "0013_mp_identity")
    with scratch_database.begin() as db:
        db.execute(text("UPDATE customer_credits SET paid_date='2026-10-16' WHERE paid"))
    migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT amount,paid,paid_date,created_at,paid_at FROM customer_credits ORDER BY id")).all() == [
            (Decimal("123.45"), True, date(2026, 10, 16), None, None),
            (Decimal("67.89"), False, None, None, None)]
    with pytest.raises(IntegrityError), scratch_database.begin() as db:
        db.execute(text("UPDATE customer_credits SET paid_date='2026-10-16' WHERE paid=false"))
    with pytest.raises(IntegrityError), scratch_database.begin() as db:
        db.execute(text("UPDATE customer_credits SET paid_at='2026-10-17 04:00+00' WHERE paid"))
