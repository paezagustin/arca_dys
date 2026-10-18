"""Sonda local sin clientes externos. No migra, factura ni modifica datos."""
import argparse
import json
import time
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from app.core.database import engine
from app.core.deployment import LOCK, control_directory


def inspect_database(connection):
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if revision != expected:
        raise RuntimeError("maintenance-required")
    # Un sending sin lock es un resultado posiblemente incierto; exige conciliación.
    uncertain = connection.scalar(text("SELECT count(*) FROM billing_requests WHERE state IN ('sending','uncertain','check_queued','retry_queued')"))
    if uncertain:
        raise RuntimeError("fiscal-reconciliation-required")
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
            return {"protocol": 1, "revision": inspect_database(connection)}
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
