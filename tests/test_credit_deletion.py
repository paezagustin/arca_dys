import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.main import app
from app.models.registers import CustomerCredit
from app.services.registers import save_register
from tests.test_closing_registers import register
from tests.test_migrations import migrate, scratch_database


@pytest.mark.parametrize("paid", ["0", "1"])
def test_remove_credit_from_every_filter_and_keep_original_record(paid):
    mistake = register(customer="Registro equivocado", amount="950", paid=paid, observation="Dato original")
    with Session(engine) as db:
        row = save_register(db, CustomerCredit, mistake)
        preserved = {
            column.name: getattr(row, column.name)
            for column in CustomerCredit.__table__.columns
            if column.name not in {"deleted_at", "version"}
        }
        identifier = row.id
        save_register(db, CustomerCredit, register(customer="Cliente que pagó", amount="200", paid="1"))

    action = f"/fiados/{identifier}/delete"
    with TestClient(app) as guest:
        assert "Eliminar fiado" not in guest.get("/fiados").text
        edit = guest.get(f"/fiados?edit={identifier}")
        assert action in edit.text and "Eliminar fiado" in edit.text
        assert "Si el cliente ya pagó, marcá el fiado como pagado" in edit.text
        token = re.search(r'name="csrf_token" value="([^"]+)"', edit.text).group(1)

        assert guest.post(action, data={"version": "1"}).status_code == 403
        assert guest.post(action, data={"csrf_token": token, "version": "9"}).status_code == 409
        assert guest.get(f"/fiados?edit={identifier}").status_code == 200

        deletion = {"csrf_token": token, "version": "1"}
        response = guest.post(action, data=deletion, follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == "/fiados?deleted=1"
        assert "Fiado eliminado." in guest.get(response.headers["location"]).text
        assert guest.post(action, data=deletion, follow_redirects=False).status_code == 303

        for paid_filter, total in {"all": 200, "no": 0, "yes": 200}.items():
            report = guest.get("/fiados", params={"paid": paid_filter})
            assert report.status_code == 200
            assert "Registro equivocado" not in report.text
            assert f'<strong class="metric">$ {total}</strong>' in report.text
        assert "Cliente que pagó" in guest.get("/fiados?paid=yes").text
        assert guest.get(f"/fiados?edit={identifier}").status_code == 404
        assert guest.post(f"/fiados/{identifier}/paid", data=deletion).status_code == 404
        replay = guest.post("/fiados", data={**mistake, "csrf_token": token})
        assert replay.status_code == 422 and "Este fiado fue eliminado" in replay.text
        edit_data = {**mistake, "id": identifier, "version": "2", "csrf_token": token}
        assert guest.post("/fiados", data=edit_data).status_code == 404

    with Session(engine) as db:
        deleted = db.get(CustomerCredit, identifier)
        assert deleted.deleted_at is not None and deleted.version == 2
        assert {name: getattr(deleted, name) for name in preserved} == preserved


def test_migration_rollback_protects_removed_credits(scratch_database):
    previous_revision = "0015_supplier_bank_details"
    migrate(scratch_database, previous_revision)
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO customer_credits(entry_key, customer, amount, observation, entry_date, version)
            VALUES ('SIM-ORIGINAL', 'Cliente ficticio', 50, 'Original', '2026-10-05', 1)"""))
    migrate(scratch_database)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT entry_key, observation, deleted_at FROM customer_credits")).one() == (
            "SIM-ORIGINAL", "Original", None)
    migrate(scratch_database, previous_revision, downgrade=True)
    migrate(scratch_database)
    with scratch_database.begin() as db:
        db.execute(text("UPDATE customer_credits SET deleted_at = now()"))
    with pytest.raises(RuntimeError, match="reactivaría fiados eliminados"):
        migrate(scratch_database, previous_revision, downgrade=True)
    with scratch_database.connect() as db:
        assert db.execute(text("SELECT deleted_at IS NOT NULL FROM customer_credits")).scalar_one() is True
