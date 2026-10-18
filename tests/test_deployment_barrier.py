"""Concurrencia real PostgreSQL, exclusivamente dentro del Compose test."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import pytest
from sqlalchemy import text
from app.core.database import engine
from app.core.deployment import operation, DeploymentBlocked
from app.services.billing import BillingService
from app.services.mp_inbox import MPInbox
from scripts.deploy_guard import probe
from app.services.fiscal_gateway import MockFiscalGateway


@pytest.fixture
def control(tmp_path, monkeypatch):
    monkeypatch.setenv("DEPLOY_CONTROL_PATH", str(tmp_path))
    (tmp_path / "protocol-v1").touch()
    return tmp_path


def test_drain_waits_for_active_operation_and_rejects_new_entries(control):
    started, finish = Event(), Event()

    def active():
        with operation(engine):
            started.set()
            assert finish.wait(10)

    with ThreadPoolExecutor() as pool:
        future = pool.submit(active)
        assert started.wait(5)
        (control / "paused").touch()
        try:
            with pytest.raises(RuntimeError, match="active-operation-timeout"):
                probe(drain=True, timeout=.1)
            with pytest.raises(DeploymentBlocked):
                with operation(engine):
                    pytest.fail("Entró después de la pausa")
        finally:
            finish.set()
        future.result(timeout=5)
    assert probe(drain=True)["revision"] == "0013_mp_identity"


def test_active_emission_finishes_once_before_drain_can_complete(control):
    entered, finish = Event(), Event()

    class SlowGateway(MockFiscalGateway):
        def emit(self, payload):
            entered.set()
            assert finish.wait(10)
            return super().emit(payload)

    with ThreadPoolExecutor() as pool:
        future = pool.submit(BillingService(gateway_factory=SlowGateway).issue,
                             manual_amount="1000", idempotency_key="active-emission")
        assert entered.wait(5)
        (control / "paused").touch()
        try:
            with pytest.raises(RuntimeError, match="active-operation-timeout"):
                probe(drain=True, timeout=.1)
            with pytest.raises(DeploymentBlocked):
                BillingService().issue(manual_amount="1000", idempotency_key="late-emission")
        finally:
            finish.set()
        assert future.result(timeout=5).state == "authorized"
    assert probe(drain=True)["protocol"] == 1
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM invoices")) == 1
        assert db.scalar(text("SELECT count(*) FROM simulated_vouchers")) == 1


@pytest.mark.parametrize("method,kwargs", [
    ("issue", {"manual_amount": "1000", "idempotency_key": "paused"}),
    ("recover", {"request_id": "anything"}), ("schedule", {"request_id": "anything"}),
    ("process_one_queued", {})])
def test_all_fiscal_entrypoints_fail_closed(control, method, kwargs):
    (control / "paused").touch()
    with pytest.raises(DeploymentBlocked):
        getattr(BillingService(), method)(**kwargs)
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM billing_requests")) == 0


def test_mp_processing_pauses_but_inbox_still_acknowledges_durable_delivery(control):
    (control / "paused").touch()
    inbox = MPInbox()
    event = inbox.receive({"type": "payment", "data": {"id": "SIM-PAUSED"}})
    with pytest.raises(DeploymentBlocked):
        inbox.process_one()
    with engine.connect() as db:
        assert db.scalar(text("SELECT state FROM mp_events WHERE id=:id"), {"id": event}) == "pending"
    assert probe(drain=True)["protocol"] == 1


@pytest.mark.parametrize("state", ["sending", "uncertain", "check_queued", "retry_queued"])
def test_fiscal_uncertainty_blocks_restart_without_changing_evidence(control, state):
    request = BillingService().issue(manual_amount="1000", idempotency_key=str(uuid4()), enqueue=True)
    with engine.begin() as db:
        db.execute(text("UPDATE billing_requests SET state=:state WHERE id=:id"), {"state": state, "id": request.request_id})
    (control / "paused").touch()
    with pytest.raises(RuntimeError, match="fiscal-reconciliation-required"):
        probe(drain=True)
    with engine.connect() as db:
        assert db.scalar(text("SELECT state FROM billing_requests")) == state


def test_missing_protocol_blocks_production_and_probe_requires_marker(control, monkeypatch):
    (control / "protocol-v1").unlink()
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(DeploymentBlocked):
        with operation(engine):
            pass
    with pytest.raises(RuntimeError, match="drain-protocol-not-installed"):
        probe()
    (control / "protocol-v1").touch()
    with pytest.raises(RuntimeError, match="pause-marker-required"):
        probe(drain=True)


def test_schema_mismatch_does_not_migrate(control):
    (control / "paused").touch()
    try:
        with engine.begin() as db:
            db.execute(text("UPDATE alembic_version SET version_num='old'"))
        with pytest.raises(RuntimeError, match="maintenance-required"):
            probe(drain=True)
    finally:
        with engine.begin() as db:
            db.execute(text("UPDATE alembic_version SET version_num='0013_mp_identity'"))


def test_schema_drift_with_same_revision_is_blocked(control):
    (control / "paused").touch()
    try:
        with engine.begin() as db:
            db.execute(text("ALTER TABLE invoices ADD COLUMN unexpected_drift integer"))
        with pytest.raises(RuntimeError, match="schema-drift-maintenance-required"):
            probe(drain=True)
    finally:
        with engine.begin() as db:
            db.execute(text("ALTER TABLE invoices DROP COLUMN unexpected_drift"))


def test_known_legacy_unique_equivalence_is_read_only_and_accepted(control):
    # El caso completo de adopción se prueba en test_migrations. Aquí se valida la
    # sonda final en el destino descartable, sin modificar el metadata global.
    (control / "paused").touch()
    try:
        with engine.begin() as db:
            db.execute(text("DROP INDEX invoices_invoice_number_key"))
            db.execute(text("ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number)"))
        assert probe(drain=True)["revision"] == "0013_mp_identity"
        with engine.connect() as db:
            assert db.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='invoices_invoice_number_key'")) == 1
    finally:
        with engine.begin() as db:
            db.execute(text("ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key"))
            db.execute(text("CREATE UNIQUE INDEX invoices_invoice_number_key ON invoices(invoice_number)"))


def test_http_returns_retryable_maintenance_response_and_health(control, client):
    (control / "paused").touch()
    response = client.post("/ARCA/requests/does-not-exist/retry")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    health = client.get("/health").json()
    assert health["paused"] is True and health["deployment_protocol"] == 1
    assert health["revision"] == "0013_mp_identity"


def test_nested_operations_do_not_deadlock_and_locks_are_released(control):
    with pytest.raises(ValueError):
        with operation(engine):
            with operation(engine):
                raise ValueError("synthetic")
    (control / "paused").touch()
    assert probe(drain=True)["protocol"] == 1
