"""Sonda local sin clientes externos. No migra, factura ni modifica datos."""
import argparse
import json
import time
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, text
from sqlalchemy.orm import Session
from pathlib import Path
from app.core import config
from app.core.database import Base, engine
from app.core.deployment import LOCK, control_directory
from app.manage import _adoption_metadata
import app.models  # Solo definiciones; no crea gateways ni cambia esquema.


def inspect_database(connection):
    connection.execute(text("SET TRANSACTION READ ONLY"))
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if revision != expected:
        raise RuntimeError("maintenance-required")
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata)
    # Misma equivalencia histórica exacta H18; SOLO metadata temporal, nunca DDL.
    metadata = _adoption_metadata(connection, metadata)
    if compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), metadata):
        raise RuntimeError("schema-drift-maintenance-required")
    # Un sending sin lock es un resultado posiblemente incierto; exige conciliación.
    uncertain = connection.scalar(text("SELECT count(*) FROM billing_requests WHERE state IN ('sending','uncertain','check_queued','retry_queued')"))
    if uncertain:
        raise RuntimeError("fiscal-reconciliation-required")
    if config.ENV == "production":
        if not all([config.ARCA_ACCESS_TOKEN, config.MP_ACCESS_TOKEN, config.MP_COLLECTOR_ID,
                    Path(config.ARCA_CRT_PATH).is_file(), Path(config.ARCA_KEY_PATH).is_file(),
                    config.MP_WEBHOOK_SECRET or len(config.MP_LEGACY_WEBHOOK_TOKEN) >= 32]):
            raise RuntimeError("production-configuration-incomplete")
        from app.services.settings import fiscal_configuration
        with Session(bind=connection) as db:
            fiscal_configuration(db)  # Lectura/validación del emisor; nunca gateway.
    return revision


def probe(drain=False, timeout=120):
    directory = control_directory()
    if not (directory / "protocol-v1").is_file():
        raise RuntimeError("drain-protocol-not-installed")
    if drain and not (directory / "paused").is_file():
        raise RuntimeError("pause-marker-required")
    with engine.connect() as connection:
        if drain:
            deadline = time.monotonic() + timeout
            while not connection.scalar(text("SELECT pg_try_advisory_lock(:lock,1)"), {"lock": LOCK}):
                connection.rollback()
                if time.monotonic() >= deadline:
                    raise RuntimeError("active-operation-timeout")
                time.sleep(.25)
            connection.commit()
        try:
            revision = inspect_database(connection)
            identity = connection.execute(text("SELECT current_database(), inet_server_addr()::text")).one()
            return {"protocol": 1, "revision": revision, "database": identity[0], "server": identity[1]}
        finally:
            if drain:
                connection.rollback()
                connection.execute(text("SELECT pg_advisory_unlock(:lock,1)"), {"lock": LOCK})
                connection.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drain", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(probe(args.drain)))
    except Exception:
        # No serializar errores SQL/DSN/configuración ni respuestas fiscales.
        raise SystemExit("Deployment guard blocked; inspect locally without exposing secrets")
