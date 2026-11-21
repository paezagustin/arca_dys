import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.main import app
from app.models.registers import CustomerCredit
from app.services.registers import save_register, delete_credit
from tests.test_closing_registers import register
from tests.test_migrations import migrate, scratch_database


@pytest.mark.parametrize("paid", ["0", "1"])
def test_legacy_soft_deletion_keeps_original_and_cannot_reactivate(paid):
    mistake = register(customer="Registro equivocado", amount="950", paid=paid, observation="Dato original")
    with Session(engine) as db:
        row = save_register(db, CustomerCredit, mistake)
        identifier = row.id
        preserved = {c.name: getattr(row,c.name) for c in CustomerCredit.__table__.columns
                     if c.name not in {"deleted_at","version"}}
        with pytest.raises(ValueError):
            delete_credit(db, identifier, "9")
        db.rollback()
        delete_credit(db, identifier, "1")
        delete_credit(db, identifier, "1")
        with pytest.raises(ValueError, match="eliminado"):
            save_register(db, CustomerCredit, mistake)
        db.rollback()
        row = db.get(CustomerCredit,identifier)
        assert row.deleted_at is not None and row.version == 2
        assert {name:getattr(row,name) for name in preserved} == preserved
    with TestClient(app) as guest:
        assert "Registro equivocado" not in guest.get("/fiados/anteriores").text
        assert guest.get(f"/fiados/anteriores/{identifier}").status_code == 404




def test_migration_rollback_protects_removed_credits(scratch_database):
    previous_revision = "0015_supplier_bank_details"
    migrate(scratch_database, previous_revision)
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO customer_credits(entry_key, customer, amount, observation, entry_date, version)
            VALUES ('SIM-ORIGINAL', 'Cliente ficticio', 50, 'Original', '2026-10-05', 1)"""))
    migrate(scratch_database, "0016_credit_deletion")
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT entry_key, observation, deleted_at FROM customer_credits")).one() == (
            "SIM-ORIGINAL", "Original", None)
    migrate(scratch_database, previous_revision, downgrade=True)
    migrate(scratch_database, "0016_credit_deletion")
    with scratch_database.begin() as db:
        db.execute(text("UPDATE customer_credits SET deleted_at = now()"))
    with pytest.raises(RuntimeError, match="reactivaría fiados eliminados"):
        migrate(scratch_database, previous_revision, downgrade=True)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT deleted_at IS NOT NULL FROM customer_credits")).scalar_one() is True
