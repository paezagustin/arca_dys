import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import IntegrityError
from app.core.database import Base, engine
from app.manage import adopt_legacy
from migrations.baseline import legacy_metadata


@pytest.fixture
def scratch_database():
    name = "migration_test_" + uuid4().hex
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    scratch = create_engine(engine.url.set(database=name))
    try:
        yield scratch
    finally:
        scratch.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


def load_export(target):
    with target.begin() as connection:
        connection.exec_driver_sql(Path("tests/fixtures/legacy_schema.sql").read_text())


def use_legacy_invoice_constraint(target):
    # Solo en la DB descartable: reproduce la variante PostgreSQL del respaldo.
    with target.begin() as connection:
        connection.execute(text("DROP INDEX invoices_invoice_number_key"))
        connection.execute(text("ALTER TABLE invoices ADD CONSTRAINT "
                                "invoices_invoice_number_key UNIQUE (invoice_number)"))


def fiscal_snapshot(target):
    # Todas las columnas originales que las migraciones publicadas conservan.
    removed = {"payments": {"id_arca"}, "error_logs": {
        "resolved", "resolved_at", "resolved_by", "resolution_notes"}}
    with target.connect() as connection:
        rows = {}
        sequences = {}
        for table in ("payments", "invoices", "payment_invoice", "error_logs"):
            columns = [column.name for column in legacy_metadata().tables[table].columns
                       if column.name not in removed.get(table, set())]
            rows[table] = connection.execute(text(
                f"SELECT {', '.join(columns)} FROM {table} ORDER BY id")).all()
            sequences[table] = connection.execute(text(
                f"SELECT last_value, is_called FROM {table}_id_seq")).one()
        return rows, sequences


def seed_fiscal_history(target):
    # Sintético: mismos conteos reportados, sin incorporar registros del respaldo real.
    with target.begin() as connection:
        connection.execute(text("""INSERT INTO payments
            (id_payment_mp,status,status_detail,mont,type_of_paid,date_approved,bill,
             registered_arca,id_arca,raw_json,created_at)
            SELECT 'SIM-MP-' || n, 'approved', 'accredited',
                CASE WHEN n % 17 = 0 THEN NULL ELSE n + 0.25 END,
                'SIM', timestamp '2026-10-01 12:34:56', n % 2 = 0, n <= 3625,
                CASE WHEN n % 2 = 0 THEN '' ELSE NULL END,
                json_build_object('simulation', true, 'id', n, 'nested', json_build_array(n, NULL)),
                timestamp '2026-10-01 12:00:00'
            FROM generate_series(1, 3876) AS n"""))
        connection.execute(text("""INSERT INTO invoices
            (invoice_number,total_amount,status,error_message,cae,cae_due_date,
             invoice_date,pdf_url,raw_afip_response,created_at)
            SELECT 'SIM-FACTURA-' || n, n * 100 + 0.50, 'approved', NULL,
                'SIM-CAE-' || n, date '2026-10-15', date '2026-10-01',
                'simulation/' || n || '.pdf',
                json_build_object('simulation', true, 'number', n,
                    'response', json_build_object('cae', 'SIM-CAE-' || n)),
                timestamp '2026-10-01 13:00:00'
            FROM generate_series(1, 181) AS n"""))
        connection.execute(text("""INSERT INTO payment_invoice (payment_id,invoice_id)
            SELECT n, ((n - 1) % 181) + 1 FROM generate_series(1, 3624) AS n"""))
        connection.execute(text("""INSERT INTO error_logs
            (created_at,source,error_type,message,resource_id,raw_data)
            VALUES ('2026-10-01','simulation','pdf','SIM-ERROR','SIM-1',
                    json_build_object('simulation', true))"""))


def migrate(target, revision="head", downgrade=False):
    config = Config("alembic.ini")
    with target.begin() as connection:
        config.attributes["connection"] = connection
        (command.downgrade if downgrade else command.upgrade)(config, revision)


def test_fresh_database_migrates_and_matches_current_models(scratch_database):
    migrate(scratch_database)
    with scratch_database.connect() as connection:
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == head
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert "logs_invoice" not in inspect(connection).get_table_names()


def test_existing_export_adopts_without_losing_rows(scratch_database):
    load_export(scratch_database)
    with scratch_database.begin() as connection:
        connection.execute(text("""INSERT INTO payments
            (id_payment_mp,status,mont,registered_arca,id_arca)
            VALUES ('SIM-LEGACY','approved',10000,true,'')"""))
        connection.execute(text("""INSERT INTO invoices
            (invoice_number,total_amount,cae,raw_afip_response)
            VALUES ('SIM-HISTORICA',10000,'SIM-CAE',CAST(:raw AS JSON))"""), {"raw": '{"legacy":true}'})
        connection.execute(text("INSERT INTO payment_invoice (payment_id,invoice_id) VALUES (1,1)"))
        connection.execute(text("""INSERT INTO error_logs
            (created_at,source,error_type,message,resolved,resolved_by,resolution_notes)
            VALUES ('2026-10-01','simulation','pdf','SIM-ERROR',false,'','  ')"""))
    adopt_legacy(scratch_database)
    with scratch_database.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), legacy_metadata()) == []
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_legacy"
    with pytest.raises(RuntimeError, match="ya tiene versionado"):
        adopt_legacy(scratch_database)
    migrate(scratch_database)
    with scratch_database.connect() as connection:
        assert connection.execute(text("SELECT id_payment_mp,mont,registered_arca FROM payments")).one() == ("SIM-LEGACY", 10000, True)
        assert connection.execute(text("SELECT invoice_number,total_amount,cae,raw_afip_response FROM invoices")).one() == ("SIM-HISTORICA", 10000, "SIM-CAE", {"legacy": True})
        assert connection.execute(text("SELECT payment_id,invoice_id FROM payment_invoice")).one() == (1, 1)
        assert connection.execute(text("SELECT source,message FROM error_logs")).one() == ("simulation", "SIM-ERROR")
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


@pytest.mark.parametrize("via_cli", [False, True], ids=["api", "cli"])
def test_existing_unique_constraint_adopts_and_migrates_to_head(scratch_database, via_cli):
    load_export(scratch_database)
    use_legacy_invoice_constraint(scratch_database)
    seed_fiscal_history(scratch_database)
    before = fiscal_snapshot(scratch_database)
    with scratch_database.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), legacy_metadata())
        assert [item[0] for item in differences] == ["remove_constraint", "add_index"]
        constraint_before = connection.execute(text("""SELECT oid, conindid
            FROM pg_constraint WHERE conrelid='invoices'::regclass
            AND conname='invoices_invoice_number_key'""")).one()
    cli_env = {**os.environ, "DATABASE_URL": scratch_database.url.render_as_string(hide_password=False)}
    if via_cli:
        result = subprocess.run([sys.executable, "-m", "app.manage", "adopt-legacy"],
                                env=cli_env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Baseline adoptado" in result.stdout
    else:
        adopt_legacy(scratch_database)
    assert fiscal_snapshot(scratch_database) == before
    with scratch_database.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_legacy"
    with pytest.raises(RuntimeError, match="ya tiene versionado"):
        adopt_legacy(scratch_database)
    if via_cli:
        result = subprocess.run(["alembic", "upgrade", "head"], env=cli_env,
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        migrate(scratch_database)
    assert fiscal_snapshot(scratch_database) == before
    with scratch_database.connect() as connection:
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == head
        assert connection.execute(text("""SELECT oid, conindid
            FROM pg_constraint WHERE conrelid='invoices'::regclass
            AND conname='invoices_invoice_number_key'""")).one() == constraint_before
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert [item[0] for item in differences] == ["remove_constraint", "add_index"]
        assert connection.execute(text("""SELECT count(*), count(*) FILTER (WHERE registered_arca)
            FROM payments""")).one() == (3876, 3625)
        assert connection.execute(text("SELECT count(*) FROM invoices")).scalar_one() == 181
        assert connection.execute(text("SELECT count(*) FROM payment_invoice")).scalar_one() == 3624
    with pytest.raises(IntegrityError):
        with scratch_database.begin() as connection:
            connection.execute(text("INSERT INTO invoices (id,invoice_number) VALUES (9999,'SIM-FACTURA-1')"))
    assert fiscal_snapshot(scratch_database) == before


@pytest.mark.parametrize("statement", [
    "ALTER TABLE invoices RENAME CONSTRAINT invoices_invoice_number_key TO unexpected_key",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "CREATE INDEX invoices_invoice_number_key ON invoices (invoice_number)",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (cae)",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number,cae)",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE payments ADD CONSTRAINT invoices_invoice_number_key UNIQUE (id_payment_mp)",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number) DEFERRABLE",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number) DEFERRABLE INITIALLY DEFERRED",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE NULLS NOT DISTINCT (invoice_number)",
    "ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key; "
        "ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number) INCLUDE (cae)",
    "ALTER TABLE invoices ADD CONSTRAINT unexpected_key UNIQUE (cae)",
    "CREATE INDEX unexpected_index ON invoices (cae)",
    "ALTER TABLE payments ADD COLUMN unexpected_column integer",
    "ALTER TABLE payments DROP COLUMN id_arca",
    "ALTER TABLE invoices ALTER COLUMN cae TYPE varchar(400)",
    "ALTER TABLE invoices ALTER COLUMN invoice_number SET NOT NULL",
    "ALTER TABLE payment_invoice DROP CONSTRAINT payment_invoice_invoice_id_fkey",
    "CREATE TABLE unexpected_table (id integer)",
], ids=["wrong-name", "missing-key", "not-unique", "wrong-column", "multiple-columns",
        "wrong-table", "deferrable", "deferred", "nulls-not-distinct", "included-column",
        "extra-constraint", "extra-index", "extra-column", "missing-column", "column-type",
        "nullability", "missing-fk", "extra-table"])
def test_unique_constraint_equivalence_does_not_hide_drift(scratch_database, statement):
    load_export(scratch_database)
    use_legacy_invoice_constraint(scratch_database)
    seed_fiscal_history(scratch_database)
    with scratch_database.begin() as connection:
        connection.exec_driver_sql(statement)
    before = fiscal_snapshot(scratch_database)
    with pytest.raises(RuntimeError, match="difiere|tablas no coinciden"):
        adopt_legacy(scratch_database)
    assert "alembic_version" not in inspect(scratch_database).get_table_names()
    assert fiscal_snapshot(scratch_database) == before


@pytest.mark.parametrize("statement", [
    "INSERT INTO logs_invoice(error) VALUES ('SIM-HISTORICO')",
    "INSERT INTO payments(id_payment_mp,status,id_arca) VALUES ('SIM-OLD','approved','SIM-VALOR')",
    "UPDATE error_logs SET resolved=true",
    "UPDATE error_logs SET resolved_at='2026-10-01'",
    "UPDATE error_logs SET resolved_by='SIM-USUARIO'",
    "UPDATE error_logs SET resolution_notes='SIM-NOTA'",
])
def test_cleanup_preserves_schema_and_data_if_unexpected_information_exists(scratch_database, statement):
    load_export(scratch_database)
    with scratch_database.begin() as connection:
        connection.execute(text("""INSERT INTO error_logs(created_at,source,error_type,message)
            VALUES ('2026-10-01','simulation','pdf','SIM-ERROR')"""))
        connection.execute(text(statement))
    adopt_legacy(scratch_database)
    with pytest.raises(RuntimeError, match="contiene información"):
        migrate(scratch_database)
    with scratch_database.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), legacy_metadata()) == []
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_legacy"
        # El rollback conserva también los valores que impidieron la migración.
        assert connection.execute(text("SELECT message FROM error_logs")).scalar_one() == "SIM-ERROR"
        if "logs_invoice" in statement:
            assert connection.execute(text("SELECT error FROM logs_invoice")).scalar_one() == "SIM-HISTORICO"
        elif "payments" in statement:
            assert connection.execute(text("SELECT id_arca FROM payments")).scalar_one() == "SIM-VALOR"
        else:
            column = statement.split("SET ")[1].split("=")[0]
            assert connection.execute(text(f"SELECT {column} FROM error_logs")).scalar_one() is not None


def test_cleanup_downgrade_restores_empty_structures_and_can_upgrade_again(scratch_database):
    migrate(scratch_database, "0002_cleanup")
    migrate(scratch_database, "0001_legacy", downgrade=True)
    with scratch_database.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), legacy_metadata()) == []
    migrate(scratch_database)
    with scratch_database.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_schema_drift_prevents_stamp(scratch_database):
    load_export(scratch_database)
    with scratch_database.begin() as connection:
        connection.execute(text("ALTER TABLE payments DROP COLUMN id_arca"))
    with pytest.raises(RuntimeError, match="difiere"):
        adopt_legacy(scratch_database)
    assert "alembic_version" not in inspect(scratch_database).get_table_names()


def test_mp_unique_identity_migration_stops_without_deleting_legacy_duplicates(scratch_database):
    migrate(scratch_database, "0003_billing")
    with scratch_database.begin() as connection:
        connection.execute(text("INSERT INTO payments(id_payment_mp,status,mont) VALUES ('SIM-DUP','approved',10000),('SIM-DUP','approved',10000)"))
    with pytest.raises(RuntimeError, match="duplicados heredados"):
        migrate(scratch_database)
    with scratch_database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM payments")).scalar_one() == 2
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003_billing"
        assert "mp_events" not in inspect(connection).get_table_names()
