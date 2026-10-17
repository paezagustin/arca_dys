"""Datos sintéticos; nunca usar los archivos privados como fixtures."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import subprocess
import sys

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.business import BusinessEntry, Supplier
from app.models.data_import import DataImport, LegacyImportSupplierMap
from app.models.payment import Payment
from app.models.invoice import Invoice
from scripts.import_business_json import FILES, import_bundle, read_bundle
from app.services.metrics import year_metrics


@pytest.fixture
def source(tmp_path):
    data = {
        "suppliers": [{"name": "Proveedor Á ficticio", "name_key": "proveedor a ficticio", "ya_presente_en_sql": True},
                      {"name": "Proveedor B ficticio", "name_key": "proveedor b ficticio"}],
        "sales": [{"fecha": "2024-02-29", "monto": "100.10"}, {"fecha": "2024-03-01", "monto": "0"}],
        "expenses": [{"fecha": "2024-02-29", "monto": "10.01", "tipo": "EN_BLANCO", "proveedor": "Proveedor Á ficticio",
                      "proveedor_name_key": "proveedor a ficticio", "proveedor_original": "Proveedor A original ficticio"},
                     {"fecha": "2024-03-01", "monto": "20.02", "tipo": "EN_NEGRO", "proveedor": "Proveedor B ficticio",
                      "proveedor_name_key": "proveedor b ficticio"}],
    }

    def write(change=None):
        copy = deepcopy(data)
        if change:
            change(copy)
        for kind, filename in FILES.items():
            (tmp_path / filename).write_text(json.dumps(copy[kind], ensure_ascii=False), encoding="utf-8")
        return read_bundle(tmp_path)
    return write


def counts():
    with Session(engine) as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Supplier, BusinessEntry, DataImport))


def test_dry_run_writes_nothing_and_apply_reconciles_metrics_and_export(source, client):
    bundle = source()
    assert bundle.summary["normalized_supplier_keys"] == 1
    assert import_bundle(engine, bundle)["status"] == "dry_run"
    assert counts() == (0, 0, 0)
    result = import_bundle(engine, bundle, apply=True)
    assert result["status"] == "applied" and result["suppliers_created"] == 2
    assert counts() == (2, 4, 1)
    with Session(engine) as db:
        sales = list(db.scalars(select(BusinessEntry).where(BusinessEntry.kind == "sale").order_by(BusinessEntry.entry_date)))
        assert [(row.entry_date, row.amount, row.cash_amount, row.mp_amount) for row in sales] == [
            (date(2024, 2, 29), Decimal("100.10"), None, None), (date(2024, 3, 1), Decimal("0.00"), None, None)]
        assert db.execute(select(Supplier.name, BusinessEntry.expense_type).join(BusinessEntry).order_by(BusinessEntry.entry_date)).all() == [
            ("Proveedor Á ficticio", "white"), ("Proveedor B ficticio", "black")]
        assert all(row.origin == "json" and not row.description for row in db.scalars(select(BusinessEntry)))
        receipt = db.scalar(select(DataImport))
        assert receipt.file_hash == bundle.digest and receipt.report["source_hashes"] == bundle.source_hashes
        assert receipt.state == "confirmed" and receipt.confirmed_at
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
        rows = year_metrics(db, 2024)
        assert rows[1]["result"] == Decimal("90.09") and rows[2]["result"] == Decimal("-20.02")
    assert client.get("/dashboard/export?year=2024&month=2").status_code == 200


def test_rerun_never_overwrites_manual_edit_and_changed_bundle_is_rejected(source):
    bundle = source()
    import_bundle(engine, bundle, apply=True)
    with Session(engine) as db:
        row = db.scalar(select(BusinessEntry).where(BusinessEntry.kind == "sale"))
        row.amount = Decimal("777.77")
        db.commit()
    assert import_bundle(engine, bundle, apply=True)["status"] == "already_applied"
    changed = source(lambda data: data["sales"][0].update(monto="99.99"))
    with pytest.raises(ValueError, match="otros datos"):
        import_bundle(engine, changed, apply=True)
    assert counts() == (2, 4, 1)
    with Session(engine) as db:
        assert db.scalar(select(BusinessEntry.amount).where(BusinessEntry.amount == Decimal("777.77"))) == Decimal("777.77")


def test_concurrent_repetition_is_one_atomic_import(source):
    bundle = source()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: import_bundle(engine, bundle, apply=True)["status"], range(2)))
    assert sorted(results) == ["already_applied", "applied"]
    assert counts() == (2, 4, 1)


def test_reconciliation_failure_rolls_back_everything(source):
    bundle = source()
    summary = deepcopy(bundle.summary)
    summary["monthly"]["2024-02"]["sale"] = "999.99"
    with pytest.raises(ValueError, match="conciliación"):
        import_bundle(engine, replace(bundle, summary=summary), apply=True)
    assert counts() == (0, 0, 0)


def test_equal_expenses_are_distinct_records(source):
    bundle = source(lambda data: data["expenses"].append(deepcopy(data["expenses"][0])))
    import_bundle(engine, bundle, apply=True)
    assert counts() == (2, 5, 1)
    with Session(engine) as db:
        assert db.scalar(select(func.sum(BusinessEntry.amount)).where(BusinessEntry.expense_type == "white")) == Decimal("20.02")


@pytest.mark.parametrize("key", ["proveedor á ficticio", "proveedor a ficticio"])
def test_existing_provider_reused_without_overwriting_fields(source, key):
    with Session(engine) as db:
        db.add(Supplier(name="Nombre guardado", name_key=key, active=False, contact="Contacto", notes="Nota", version=4))
        db.commit()
    result = import_bundle(engine, source(), apply=True)
    assert result["suppliers_created"] == 1 and result["suppliers_reused"] == 1
    with Session(engine) as db:
        row = db.scalar(select(Supplier).where(Supplier.name_key == key))
        assert (row.name, row.active, row.contact, row.notes, row.version) == ("Nombre guardado", False, "Contacto", "Nota", 4)


def test_ambiguous_existing_providers_are_not_merged(source):
    with Session(engine) as db:
        db.add_all([Supplier(name="Uno", name_key="proveedor á ficticio"), Supplier(name="Dos", name_key="proveedor a ficticio")])
        db.commit()
    with pytest.raises(ValueError, match="ambiguos"):
        import_bundle(engine, source(), apply=True)
    assert counts() == (2, 0, 0)


def test_existing_movement_in_import_period_blocks_load_without_deletion(source):
    with Session(engine) as db:
        db.add(BusinessEntry(entry_key="manual", kind="expense", entry_date=date(2024, 3, 1), amount=Decimal("1.01"), expense_type="black"))
        db.commit()
    with pytest.raises(ValueError, match="período"):
        import_bundle(engine, source(), apply=True)
    assert counts() == (0, 1, 0)


@pytest.mark.parametrize("amount", [True, None, "NaN", "Infinity", "-1", "1.001", "10000000000000000", "1.000,50", ""])
def test_invalid_amounts_are_rejected_before_any_db_write(source, amount):
    with pytest.raises(ValueError, match="importe"):
        source(lambda data: data["sales"][0].update(monto=amount))
    assert counts() == (0, 0, 0)


@pytest.mark.parametrize("change,match", [
    (lambda data: data["sales"][0].update(fecha="2023-02-29"), "fecha"),
    (lambda data: data["sales"][0].update(fecha="20240229"), "fecha"),
    (lambda data: data["sales"].append(data["sales"][0]), "una venta"),
    (lambda data: data["expenses"][0].update(monto="0"), "importe"),
    (lambda data: data["expenses"][0].update(tipo="otro"), "tipo"),
    (lambda data: data["expenses"][0].update(tipo=[]), "tipo"),
    (lambda data: data["expenses"][0].update(proveedor_name_key="desconocido"), "correspondencia"),
    (lambda data: data["expenses"][0].update(proveedor="Otro"), "no coinciden"),
    (lambda data: data["suppliers"].append(data["suppliers"][0]), "duplicados"),
    (lambda data: data["suppliers"][0].update(ya_presente_en_sql="sí"), "booleano"),
])
def test_bad_input_fails_as_a_whole(source, change, match):
    with pytest.raises(ValueError, match=match):
        source(change)
    assert counts() == (0, 0, 0)


def test_invalid_json_duplicate_fields_and_missing_files(source, tmp_path):
    source()
    file = tmp_path / FILES["sales"]
    file.write_text('[{"fecha":"2024-01-01","monto":"1","monto":"2"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="campo repetido"):
        read_bundle(tmp_path)
    file.unlink()
    with pytest.raises(OSError):
        read_bundle(tmp_path)


def test_console_commands_validate_apply_repeat_and_report_invalid_input(source, tmp_path):
    source()
    command = [sys.executable, "-m", "scripts.import_business_json", "--directory", str(tmp_path)]
    dry = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(dry.stdout)["status"] == "dry_run" and counts() == (0, 0, 0)
    applied = subprocess.run(command + ["--apply"], capture_output=True, text=True, check=True)
    assert json.loads(applied.stdout)["status"] == "applied" and counts() == (2, 4, 1)
    repeat = subprocess.run(command + ["--apply"], capture_output=True, text=True, check=True)
    assert json.loads(repeat.stdout)["status"] == "already_applied" and counts() == (2, 4, 1)
    (tmp_path / FILES["sales"]).write_text("{}", encoding="utf-8")
    bad = subprocess.run(command + ["--apply"], capture_output=True, text=True)
    assert bad.returncode == 2 and "lista no vacía" in bad.stderr and "Traceback" not in bad.stderr
    assert counts() == (2, 4, 1)


def test_existing_import_metadata_is_preserved_and_protects_supplier_delete(source, client):
    import_bundle(engine, source(), apply=True)
    with Session(engine) as db:
        receipt = db.scalar(select(DataImport))
        supplier = Supplier(name="Legado ficticio", name_key="legado ficticio")
        db.add(supplier)
        db.flush()
        supplier_id = supplier.id
        db.add(LegacyImportSupplierMap(batch_id=receipt.id, label="Referencia anterior", supplier_id=supplier_id, actor="test"))
        db.commit()
    response = client.post(f"/business/suppliers/{supplier_id}/delete", data={"version": "1"})
    assert response.status_code == 422 and "registros vinculados" in response.text and "DELETE FROM" not in response.text
    with Session(engine) as db:
        assert db.get(Supplier, supplier_id) is not None
        assert db.scalar(select(func.count()).select_from(LegacyImportSupplierMap)) == 1


def test_retired_excel_routes_are_unavailable_and_navigation_has_no_import(client):
    for url in ("/business/imports", "/business/imports/ficticio", "/business/imports/ficticio/confirm", "/dashboard/history"):
        assert client.get(url).status_code == 404
        assert client.post(url).status_code == 404
    for url in ("/business", "/dashboard"):
        page = client.get(url)
        assert page.status_code == 200
        assert "/business/imports" not in page.text and "/dashboard/history" not in page.text
    assert client.get("/dashboard/export?year=2024&month=2").status_code == 200
