"""Operaciones explícitas de esquema. Nunca emite facturas ni consulta pagos."""
import argparse
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from app.core.database import engine
from migrations.baseline import legacy_metadata

BASELINE = "0001_legacy"
TABLES = {"payments", "invoices", "payment_invoice", "error_logs", "logs_invoice"}


def adopt_legacy(target_engine=engine):
    with target_engine.begin() as connection:
        inspector = inspect(connection)
        actual = set(inspector.get_table_names())
        if "alembic_version" in actual:
            raise RuntimeError("La base ya tiene versionado. Usar alembic current/upgrade, no volver a adoptar.")
        if actual != TABLES:
            raise RuntimeError("Las tablas no coinciden con el baseline; revisar antes de adoptar")
        differences = compare_metadata(MigrationContext.configure(connection), legacy_metadata())
        if differences:
            descriptions = [str(item[0]) for item in differences]
            raise RuntimeError("El esquema difiere del baseline: " + ", ".join(descriptions))
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.stamp(config, BASELINE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["adopt-legacy"])
    parser.parse_args()
    adopt_legacy()
    print("Baseline adoptado; no se borraron tablas ni registros")


if __name__ == "__main__":
    main()
