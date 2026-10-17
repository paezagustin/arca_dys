"""Transición explícita v1, atómica, de 0003 a 0013 con duplicados MP intactos.

0004_mp permanece inmutable y sigue rechazando duplicados en upgrade ordinario.
Este puente aplica su contrato de esquema EXCEPTO el índice único incompatible,
lo comprueba antes de registrar 0004 y continúa a 0013 en la MISMA transacción.
Nunca se debe ejecutar stamp manual ni iniciar la aplicación en el estado puente.
"""
from datetime import datetime, timezone
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from app.core.database import Base, engine
from app.manage import _adoption_metadata
from migrations.baseline import legacy_metadata

TARGET = "0013_mp_identity"
RECEIPT = "legacy-mp-bridge-v1"
REMOVED = {"payments": {"id_arca"}, "error_logs": {
    "resolved", "resolved_at", "resolved_by", "resolution_notes"}}


class MetadataOperations:
    def __init__(self, metadata):
        self.metadata = metadata

    def create_table(self, name, *columns):
        return sa.Table(name, self.metadata, *columns)

    def create_index(self, name, table, columns, **kwargs):
        return sa.Index(name, *[self.metadata.tables[table].c[c] for c in columns], **kwargs)


def _billing_schema(ops):
    # Contrato congelado de 0003; independiente de futuras ampliaciones del ORM.
    ops.create_table("billing_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(100), unique=True, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("point", sa.Integer(), nullable=False),
        sa.Column("voucher_type", sa.Integer(), nullable=False),
        sa.Column("voucher_number", sa.Integer()),
        *[sa.Column(name, sa.JSON(), nullable=False) for name in
          ("payment_ids", "payment_snapshot", "fiscal_snapshot")],
        sa.Column("payload", sa.JSON()), sa.Column("response", sa.JSON()), sa.Column("error", sa.Text()),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    ops.create_table("billing_reservations",
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("billing_requests.id"), nullable=False))
    ops.create_table("simulated_vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in ("point", "voucher_type", "number")],
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("response", sa.JSON(), nullable=False),
        sa.UniqueConstraint("point", "voucher_type", "number", name="uq_simulated_voucher"))


def _mp_schema(ops):
    # DDL equivalente a 0004, salvo el índice de payments, que permanece NO único.
    ops.create_table("mp_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dedup_key", sa.String(64), unique=True, nullable=False),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("resource", sa.String(200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("error", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)))
    ops.create_index("ix_mp_events_queue", "mp_events", ["state", "next_attempt_at"])
    ops.create_table("payment_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("mp_events.id"), nullable=False),
        sa.Column("previous_status", sa.String(50)), sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def _stage_metadata(connection, *, after_bridge=False):
    metadata = sa.MetaData()
    for source in legacy_metadata().sorted_tables:
        if source.name == "logs_invoice":
            continue
        table = sa.Table(source.name, metadata, *[
            sa.Column(c.name, c.type, *[sa.ForeignKey(f.target_fullname) for f in c.foreign_keys],
                      primary_key=c.primary_key, nullable=c.nullable)
            for c in source.columns if c.name not in REMOVED.get(source.name, set())])
        for index in source.indexes:
            sa.Index(index.name, *[table.c[c.name] for c in index.columns], unique=index.unique)
    metadata.tables["invoices"].append_column(sa.Column("fiscal_snapshot", sa.JSON()))
    _billing_schema(MetadataOperations(metadata))
    if after_bridge:
        metadata.tables["payments"].append_column(sa.Column("provider_updated_at", sa.DateTime(timezone=True)))
        _mp_schema(MetadataOperations(metadata))
    return _adoption_metadata(connection, metadata)


def _check_schema(connection, metadata):
    differences = compare_metadata(MigrationContext.configure(connection), metadata)
    if differences:
        raise RuntimeError("Transición MP detenida por diferencias de esquema; no usar stamp manual")


def _hash(connection, query):
    return connection.scalar(sa.text("SELECT encode(sha256(convert_to(coalesce(string_agg(value, chr(10) "
        "ORDER BY id), ''), 'UTF8')), 'hex') FROM (" + query + ") AS rows"))


def integrity_report(connection):
    """Solo SELECT: cantidades y huellas, sin IDs externos, nombres ni JSON crudos."""
    hashes, sequences = {}, {}
    for table in ("payments", "invoices", "payment_invoice", "error_logs"):
        fields = []
        for column in legacy_metadata().tables[table].columns:
            if column.name in REMOVED.get(table, set()):
                continue
            name = column.name
            if name in {"mont", "total_amount"}:
                name = f"round({name}::numeric, 2)"
            elif isinstance(column.type, sa.JSON):
                name += "::text"
            fields.append(name)
        if table == "invoices":
            columns = {column["name"] for column in sa.inspect(connection).get_columns(table)}
            fields.append("fiscal_snapshot::text" if "fiscal_snapshot" in columns else "NULL::text")
        hashes[table] = _hash(connection,
            f"SELECT id, json_build_array({', '.join(fields)})::text AS value FROM {table}")
        sequences[table] = list(connection.execute(sa.text(
            f"SELECT last_value, is_called FROM {table}_id_seq")).one())
    controls = sa.MetaData()
    _billing_schema(MetadataOperations(controls))
    tables = set(sa.inspect(connection).get_table_names())
    for name, table in controls.tables.items():
        fields = [column.name + ("::text" if isinstance(column.type, sa.JSON) else "") for column in table.columns]
        key = next(iter(table.primary_key.columns)).name
        query = (f"SELECT {key} AS id, json_build_array({', '.join(fields)})::text AS value FROM {name}"
                 if name in tables else "SELECT 0 AS id, ''::text AS value WHERE false")
        hashes[name] = _hash(connection, query)
    audited = connection.scalar(sa.text("SELECT to_regclass('money_migration_audit') IS NOT NULL"))
    for table, amount in (("payments", "mont"), ("invoices", "total_amount")):
        query = (f"SELECT record_id AS id, json_build_array(record_id, original_text)::text AS value "
                 f"FROM money_migration_audit WHERE table_name='{table}'") if audited else (
                 f"SELECT id, json_build_array(id, {amount}::text)::text AS value FROM {table}")
        hashes[table + "_original_amounts"] = _hash(connection, query)
    counts = dict(connection.execute(sa.text("""SELECT 'payments', count(*) FROM payments
        UNION ALL SELECT 'registered', count(*) FROM payments WHERE registered_arca
        UNION ALL SELECT 'invoices', count(*) FROM invoices
        UNION ALL SELECT 'links', count(*) FROM payment_invoice
        UNION ALL SELECT 'errors', count(*) FROM error_logs""")).all())
    groups, rows = connection.execute(sa.text("""SELECT count(*), coalesce(sum(n),0)::bigint FROM
        (SELECT count(*) n FROM payments GROUP BY id_payment_mp HAVING count(*) > 1) d""")).one()
    return {"counts": counts, "duplicate_groups": groups, "duplicate_rows": rows,
            "additional_rows": rows - groups, "sha256": hashes, "sequences": sequences}


def audit_legacy_mp(target_engine=engine):
    with target_engine.connect() as connection:
        connection.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return integrity_report(connection)


def check_mp_identities(connection):
    invalid = connection.scalar(sa.text("""WITH groups AS (
        SELECT id_payment_mp, count(*) n, min(id) only_id FROM payments GROUP BY id_payment_mp)
        SELECT count(*) FROM groups g FULL JOIN mp_payment_identities i USING(id_payment_mp)
        WHERE g.id_payment_mp IS NULL OR i.id_payment_mp IS NULL
          OR (g.n>1 AND (NOT i.legacy_duplicate OR i.payment_id IS NOT NULL))
          OR (g.n=1 AND (i.legacy_duplicate OR i.payment_id IS DISTINCT FROM g.only_id))"""))
    triggers = connection.scalar(sa.text("""SELECT count(*) FROM pg_trigger
        WHERE tgrelid='payments'::regclass AND tgenabled='O' AND NOT tgisinternal
          AND tgname IN ('mp_register_payment_identity','mp_protect_payment_history')"""))
    report = {"invalid_groups": invalid, "protected_triggers": triggers,
              "legacy_snapshots": connection.scalar(sa.text("SELECT count(*) FROM mp_legacy_payment_snapshots")),
              "blocked_groups": connection.scalar(sa.text("SELECT count(*) FROM mp_payment_identities WHERE legacy_duplicate"))}
    if invalid or triggers != 2:
        raise RuntimeError("La identidad MP o sus protecciones no coinciden; detener y revisar")
    return report


def _check_initial_snapshots(connection, expected_count):
    report = check_mp_identities(connection)
    different = connection.scalar(sa.text("""SELECT count(*) FROM payments p
        FULL JOIN mp_legacy_payment_snapshots s ON s.payment_id=p.id
        WHERE p.id IS NULL OR s.payment_id IS NULL OR s.snapshot::text IS DISTINCT FROM row_to_json(p)::text"""))
    if report["legacy_snapshots"] != expected_count or different:
        raise RuntimeError("Los snapshots MP no coinciden con las filas originales; detener y revisar")


def migrate_legacy_mp(target_engine=engine):
    config = Config("alembic.ini")
    if ScriptDirectory.from_config(config).get_current_head() != TARGET:
        raise RuntimeError("Revisar el puente MP para el nuevo head antes de continuar")
    with target_engine.begin() as connection:
        connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(sa.text("LOCK TABLE payments, invoices, payment_invoice, error_logs IN ACCESS EXCLUSIVE MODE"))
        versions = connection.scalars(sa.text("SELECT version_num FROM alembic_version")).all()
        if versions == [TARGET]:
            from app.models.mp_identity import MPLegacyTransition
            receipt = connection.scalar(sa.select(MPLegacyTransition.report).where(MPLegacyTransition.id == RECEIPT))
            if receipt is None or receipt != integrity_report(connection):
                raise RuntimeError("La transición ya terminó o cambió la base; revisar sin repetir escrituras")
            _check_initial_snapshots(connection, receipt["counts"]["payments"])
            return receipt
        if len(versions) != 1 or versions[0] not in {"0001_legacy", "0002_cleanup", "0003_billing"}:
            raise RuntimeError("El puente MP requiere una base adoptada en 0001, 0002 o 0003")
        source = versions[0]
        before = integrity_report(connection)
        if not before["duplicate_groups"]:
            raise RuntimeError("Sin duplicados históricos: usar alembic upgrade head ordinario")
        config.attributes["connection"] = connection
        command.upgrade(config, "0003_billing")
        _check_schema(connection, _stage_metadata(connection))
        if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM billing_requests WHERE state NOT IN ('authorized','rejected'))")):
            raise RuntimeError("Hay solicitudes fiscales activas; revisar antes de la transición MP")
        operations = Operations(MigrationContext.configure(connection))
        operations.add_column("payments", sa.Column("provider_updated_at", sa.DateTime(timezone=True)))
        _mp_schema(operations)
        _check_schema(connection, _stage_metadata(connection, after_bridge=True))
        # Registro controlado del contrato alternativo, nunca un stamp sin DDL.
        # No puede observarse 0004 con duplicados fuera de esta transacción.
        command.stamp(config, "0004_mp")
        command.upgrade(config, TARGET)
        current = sa.MetaData()
        for table in Base.metadata.sorted_tables:
            table.to_metadata(current)
        _check_schema(connection, _adoption_metadata(connection, current))
        _check_initial_snapshots(connection, before["counts"]["payments"])
        after = integrity_report(connection)
        if after != before:
            raise RuntimeError("La integridad fiscal no coincide; se revierte toda la transición MP")
        from app.models.mp_identity import MPLegacyTransition
        connection.execute(sa.insert(MPLegacyTransition).values(id=RECEIPT, source_revision=source,
            target_revision=TARGET, report=after, completed_at=datetime.now(timezone.utc)))
        return after
