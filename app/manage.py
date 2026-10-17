"""Operaciones explícitas de esquema. Nunca emite facturas ni consulta pagos."""
import argparse
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import UniqueConstraint, inspect, text
from app.core.database import engine
from migrations.baseline import legacy_metadata

BASELINE = "0001_legacy"
TABLES = {"payments", "invoices", "payment_invoice", "error_logs", "logs_invoice"}


def _adoption_metadata(connection, metadata=None):
    """Normaliza solo la equivalencia conocida, en memoria y para comparar.

    No ejecuta DDL ni cambia el baseline congelado. Las demás diferencias siguen
    pasando por la comparación completa de Alembic.
    """
    metadata = legacy_metadata() if metadata is None else metadata
    if connection.dialect.name != "postgresql":
        return metadata
    key = "invoices_invoice_number_key"
    equivalent = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM pg_catalog.pg_constraint AS c
            JOIN pg_catalog.pg_attribute AS a
              ON a.attrelid = c.conrelid AND a.attname = 'invoice_number'
            JOIN pg_catalog.pg_index AS i ON i.indexrelid = c.conindid
            JOIN pg_catalog.pg_class AS idx ON idx.oid = c.conindid
            WHERE c.conrelid = to_regclass('invoices')
              AND c.conname = :key AND c.contype = 'u'
              AND c.conkey = ARRAY[a.attnum]
              AND NOT c.condeferrable AND NOT c.condeferred AND c.convalidated
              AND idx.relname = :key
              AND i.indisunique AND i.indisvalid AND i.indisready AND i.indimmediate
              AND NOT i.indnullsnotdistinct
              AND i.indnkeyatts = 1 AND i.indnatts = 1
              AND i.indexprs IS NULL AND i.indpred IS NULL
        )
    """), {"key": key}).scalar_one()
    if equivalent:
        invoices = metadata.tables["invoices"]
        index = next(index for index in invoices.indexes if index.name == key)
        invoices.indexes.remove(index)
        invoices.append_constraint(UniqueConstraint("invoice_number", name=key))
    return metadata


def adopt_legacy(target_engine=engine):
    with target_engine.begin() as connection:
        inspector = inspect(connection)
        actual = set(inspector.get_table_names())
        if "alembic_version" in actual:
            raise RuntimeError("La base ya tiene versionado. Usar alembic current/upgrade, no volver a adoptar.")
        if actual != TABLES:
            raise RuntimeError("Las tablas no coinciden con el baseline; revisar antes de adoptar")
        differences = compare_metadata(MigrationContext.configure(connection), _adoption_metadata(connection))
        if differences:
            descriptions = [str(item[0]) for item in differences]
            raise RuntimeError("El esquema difiere del baseline: " + ", ".join(descriptions))
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.stamp(config, BASELINE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["adopt-legacy", "create-user", "audit-mp-legacy", "migrate-legacy-mp", "check-mp-identities"])
    parser.add_argument("--username")
    parser.add_argument("--role", choices=["admin", "operator"], default="admin")
    args = parser.parse_args()
    if args.action == "adopt-legacy":
        adopt_legacy()
        print("Baseline adoptado; no se borraron tablas ni registros")
    elif args.action in {"audit-mp-legacy", "migrate-legacy-mp"}:
        import json
        from migrations.mp_legacy_bridge import audit_legacy_mp, migrate_legacy_mp
        report = audit_legacy_mp() if args.action == "audit-mp-legacy" else migrate_legacy_mp()
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    elif args.action == "check-mp-identities":
        import json
        from migrations.mp_legacy_bridge import check_mp_identities
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            print(json.dumps(check_mp_identities(connection), sort_keys=True))
    else:
        from getpass import getpass
        from sqlalchemy.orm import Session
        from app.services.access import create_user
        if not args.username:
            parser.error("create-user requiere --username")
        password = getpass("Contraseña (al menos 12 caracteres): ")
        if password != getpass("Repetir contraseña: "):
            raise ValueError("Las contraseñas no coinciden")
        with Session(engine) as db:
            create_user(db, args.username, password, args.role)
        print("Usuario creado. No se iniciaron operaciones con proveedores.")


if __name__ == "__main__":
    main()
