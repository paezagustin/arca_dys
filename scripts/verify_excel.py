"""Conciliación privada en una DB efímera. No imprime importes ni copia el archivo."""
import os
from pathlib import Path
import sys
from uuid import uuid4
from decimal import Decimal
from hashlib import sha256
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.core.database import engine
from app.models.business import BusinessEntry
from app.models.imports import ImportRow
from app.services.excel_reader import read_excel
from app.services.excel_import import prepare_import, confirm_import


def verify(path):
    if os.environ.get("ENV") != "test" or os.environ.get("INTEGRATIONS_MODE") != "mock" or engine.url.host != "postgres" or engine.url.database != "arca_dys_test":
        raise RuntimeError("Verificación habilitada solo en el Compose test aislado")
    content = Path(path).read_bytes()
    checksum = sha256(content).digest()
    dataset = "verificacion-privada"
    parsed = read_excel(content, dataset)
    name = "excel_verify_" + uuid4().hex
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
        db.execute(text(f'CREATE DATABASE "{name}"'))
    scratch = create_engine(engine.url.set(database=name))
    try:
        config = Config("alembic.ini")
        with scratch.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with Session(scratch) as db:
            batch = prepare_import(db, content, dataset, "original-privado.xlsx", "verificación", parsed)
            identifier = batch.id
            confirm_import(db, identifier, "verificación")
            counts = dict(db.execute(select(ImportRow.state, func.count()).where(ImportRow.batch_id == identifier,
                ImportRow.kind.in_(["sale", "expense"])).group_by(ImportRow.state)).all())
            original = batch.report["source_totals"]
            for month, values in original.items():
                for key, expected in values.items():
                    query = select(func.coalesce(func.sum(BusinessEntry.amount), 0)).where(
                        func.to_char(BusinessEntry.entry_date, "YYYY-MM") == month,
                        BusinessEntry.kind == ("sale" if key == "sales" else "expense"))
                    if key != "sales":
                        query = query.where(BusinessEntry.classification == ("COMPRAS EN BLANCO" if key == "D" else "COMPRAS EN NEGRO"))
                    if db.scalar(query) != Decimal(expected):
                        raise RuntimeError("La conciliación mensual requiere revisión; no se alteró el original")
            count = db.scalar(select(func.count()).select_from(BusinessEntry))
            assert prepare_import(db, content, dataset, "otro-nombre.xlsx", "verificación", parsed).id == identifier
            confirm_import(db, identifier, "verificación")
            assert db.scalar(select(func.count()).select_from(BusinessEntry)) == count
            assert not db.scalar(select(func.count()).select_from(ImportRow).where(ImportRow.sheet.notin_(["ingresos y egresos", "dashboard"])))
            original_rows = {(r["sheet"], r["row_number"], r["slot"]): r["raw"] for r in parsed[0]}
            for row in db.scalars(select(ImportRow)):
                assert row.raw == original_rows[(row.sheet, row.row_number, row.slot)]
            assert sha256(Path(path).read_bytes()).digest() == checksum
            print(f"Conciliación mensual exacta: {len(original)} meses; {count} registros; {counts.get('review',0)} filas conservadas para revisión.")
            print("Reimportación idempotente, celdas originales e históricos íntegros, sueldos excluidos y archivo sin cambios: OK.")
    finally:
        scratch.dispose()
        if not name.startswith("excel_verify_") or not name[len("excel_verify_"):].isalnum():
            raise RuntimeError("Nombre efímero inesperado; no se eliminó ninguna base")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
            db.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


if __name__ == "__main__":
    verify(sys.argv[1])
