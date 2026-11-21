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
from app.services.registers import save_register, mark_credit_paid
from tests.test_closing_registers import register
from tests.test_migrations import scratch_database, migrate


def freeze_clock(monkeypatch, day, hour, minute):
    instant = datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.registers.utcnow", lambda: instant)
    return instant


def test_legacy_transition_keeps_buenos_aires_dates_and_idempotent_mark(monkeypatch):
    """Contrato del registro anterior, conservado para ensayos de históricos."""
    created = freeze_clock(monkeypatch, 16, 12, 15)
    with Session(engine) as db:
        identifier = save_register(db, CustomerCredit, register(entry_date="2026-10-10")).id
    paid = freeze_clock(monkeypatch, 17, 2, 30)
    with Session(engine) as db:
        mark_credit_paid(db, identifier, "1")
    freeze_clock(monkeypatch, 17, 4, 0)
    with Session(engine) as db:
        mark_credit_paid(db, identifier, "1")
        row = db.get(CustomerCredit, identifier)
        assert row.paid_date == date(2026, 10, 16) and row.paid_at == paid
        assert row.created_at == created and row.version == 2


def test_legacy_form_dates_survive_edit_and_clear_only_on_explicit_reopening(monkeypatch):
    created = freeze_clock(monkeypatch, 16, 18, 45)
    data = register(paid="1", paid_date="1900-01-01", created_at="1900-01-01", paid_at="1900-01-01")
    with Session(engine) as db:
        identifier = save_register(db, CustomerCredit, data).id
        assert save_register(db, CustomerCredit, data).id == identifier
        row = save_register(db, CustomerCredit, dict(data, version="1", observation="Corregida"), identifier)
        assert row.paid_at == row.created_at == created
        assert row.paid_date == date(2026, 10, 16)
        row = save_register(db, CustomerCredit, dict(data, version="2", paid="0"), identifier)
        assert row.paid_date is None and row.paid_at is None
    paid_again = freeze_clock(monkeypatch, 17, 12, 10)
    with Session(engine) as db:
        row = save_register(db, CustomerCredit, dict(data, version="3", paid="1"), identifier)
        assert row.paid_date == date(2026, 10, 17) and row.paid_at == paid_again
        assert row.created_at == created


@pytest.mark.parametrize("old_date", [None, date(2020, 1, 2)])
def test_legacy_paid_record_never_invents_unknown_times(old_date):
    with Session(engine) as db:
        row = CustomerCredit(entry_key="SIM-LEGACY-PAID", entry_date=date(2020,1,1), amount=Decimal("10.25"),
            customer="Cliente ficticio anterior", observation="", paid=True, paid_date=old_date, version=1)
        db.add(row); db.commit()
        mark_credit_paid(db, row.id, "1")
        assert row.paid_date == old_date and row.paid_at is None and row.created_at is None










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
