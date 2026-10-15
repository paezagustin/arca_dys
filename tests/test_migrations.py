from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text, inspect
from app.core.database import engine
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


def test_fresh_database_migrates_and_matches_export(scratch_database):
    config = Config("alembic.ini")
    with scratch_database.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_legacy"
        assert compare_metadata(MigrationContext.configure(connection), legacy_metadata()) == []


def test_existing_export_adopts_without_losing_rows(scratch_database):
    load_export(scratch_database)
    with scratch_database.begin() as connection:
        connection.execute(text("INSERT INTO payments (id_payment_mp,status,mont,registered_arca) VALUES ('SIM-LEGACY','approved',10000,false)"))
    adopt_legacy(scratch_database)
    with scratch_database.connect() as connection:
        assert connection.execute(text("SELECT id_payment_mp,mont,registered_arca FROM payments")).one() == ("SIM-LEGACY", 10000, False)
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_legacy"
    with pytest.raises(RuntimeError, match="ya tiene versionado"):
        adopt_legacy(scratch_database)


def test_schema_drift_prevents_stamp(scratch_database):
    load_export(scratch_database)
    with scratch_database.begin() as connection:
        connection.execute(text("ALTER TABLE payments DROP COLUMN id_arca"))
    with pytest.raises(RuntimeError, match="difiere"):
        adopt_legacy(scratch_database)
    assert "alembic_version" not in inspect(scratch_database).get_table_names()
