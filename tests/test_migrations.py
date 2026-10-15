from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text, inspect
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
