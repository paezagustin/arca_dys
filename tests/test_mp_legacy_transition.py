"""Datos sintéticos; nunca lee ni restaura el respaldo real."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
import json
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.manage import _adoption_metadata, adopt_legacy
from app.models.billing import BillingRequest, BillingReservation
from app.models.mp_event import MPEvent, PaymentChange
from app.models.mp_identity import MPPaymentIdentity, MPLegacyPaymentSnapshot, MPLegacyTransition
from app.models.payment import Payment
from app.services.billing import BillingConflict, BillingService
from app.services.billing_preview import preview_invoice
from app.services.day_closing import unbilled_mp_total
from app.services.listings import parse_filters, payment_statement
from app.services.mp_inbox import MPInbox
from app.services.metrics import period_metrics
from migrations.mp_legacy_bridge import audit_legacy_mp, integrity_report, migrate_legacy_mp, TARGET
from tests.test_migrations import (scratch_database, migrate, load_export,
    use_legacy_invoice_constraint, seed_fiscal_history, fiscal_snapshot)
from tests.test_mp_inbox import resource


def seed_legacy_duplicates(target, *, invoice_constraint=True):
    load_export(target)
    if invoice_constraint:
        use_legacy_invoice_constraint(target)
    seed_fiscal_history(target)
    unbilled = list(range(1, 10)) + [12, 15, 18, 21, 24]
    with target.begin() as db:
        # 8 triples y 32 pares: 40 grupos, 88 filas, 48 filas adicionales.
        db.execute(text("""UPDATE payments SET
            id_payment_mp='SIM-DUP-' || CASE WHEN id <= 24 THEN ((id-1)/3)+1 ELSE ((id-25)/2)+9 END,
            mont=(CASE WHEN id <= 24 THEN ((id-1)/3)+1 ELSE ((id-25)/2)+9 END)*1000+0.25
            WHERE id <= 88"""))
        db.execute(text("UPDATE payments SET registered_arca=false WHERE id=ANY(:ids)"), {"ids": unbilled})
        db.execute(text("UPDATE payments SET registered_arca=true WHERE id BETWEEN 3626 AND 3639"))
        # Reubica solamente el fixture antes de tomar la evidencia inicial.
        db.execute(text("UPDATE payment_invoice SET payment_id=3625+array_position(:ids, payment_id) WHERE payment_id=ANY(:ids)"), {"ids": unbilled})
        db.execute(text("""UPDATE payment_invoice AS l SET invoice_id=((
            CASE WHEN p.id <= 24 THEN ((p.id-1)/3)+1 ELSE ((p.id-25)/2)+9 END)-1)%31+1
            FROM payments p WHERE l.payment_id=p.id AND p.id <= 88"""))
        db.execute(text("UPDATE payments SET status='pending' WHERE id=10"))
        db.execute(text("UPDATE payments SET date_approved='2026-10-02 12:34:56' WHERE id=13"))
        db.execute(text("""UPDATE payments SET raw_json=json_build_object('simulation',true,'group',id_payment_mp)
            WHERE id BETWEEN 67 AND 88"""))
        # Grupo 29 ocupa 65/66; quedan exactamente 29 grupos con JSON distinto.
        db.execute(text("UPDATE invoices SET raw_afip_response=NULL"))
        db.execute(text("""INSERT INTO error_logs(created_at,source,error_type,message,raw_data)
            SELECT timestamp '2026-10-01','simulation','legacy','SIM-ERROR-' || n,
            json_build_object('simulation',true,'n',n) FROM generate_series(2,175) AS n"""))
    adopt_legacy(target)


def assert_reported_fixture(target):
    report = audit_legacy_mp(target)
    assert report["counts"] == {"payments": 3876, "registered": 3625, "invoices": 181, "links": 3624, "errors": 175}
    assert (report["duplicate_groups"], report["duplicate_rows"], report["additional_rows"]) == (40, 88, 48)
    with target.connect() as db:
        assert db.execute(text("""WITH dup AS (SELECT id_payment_mp FROM payments
                GROUP BY id_payment_mp HAVING count(*)>1)
            SELECT count(*) FILTER (WHERE p.registered_arca), count(l.id), count(DISTINCT l.invoice_id)
            FROM payments p JOIN dup USING(id_payment_mp) LEFT JOIN payment_invoice l ON l.payment_id=p.id""")).one() == (74, 74, 31)
        assert db.execute(text("""SELECT count(*) FILTER (WHERE amounts>1), count(*) FILTER (WHERE statuses>1),
            count(*) FILTER (WHERE dates>1), count(*) FILTER (WHERE flags>1), count(*) FILTER (WHERE raws>1)
            FROM (SELECT count(DISTINCT mont) amounts, count(DISTINCT status) statuses,
                count(DISTINCT date_approved) dates, count(DISTINCT registered_arca) flags,
                count(DISTINCT raw_json::text) raws
                FROM payments GROUP BY id_payment_mp HAVING count(*)>1) d""")).one() == (0, 1, 1, 5, 29)
        assert db.scalar(text("""SELECT count(*) FROM (SELECT p.id_payment_mp FROM payments p
            JOIN payment_invoice l ON l.payment_id=p.id GROUP BY p.id_payment_mp
            HAVING count(DISTINCT l.invoice_id)>1) d""")) == 0
    return report


@pytest.mark.parametrize("source", ["0001_legacy", "0002_cleanup", "0003_billing"])
def test_bridge_preserves_complete_report_and_original_rows(scratch_database, source):
    seed_legacy_duplicates(scratch_database)
    migrate(scratch_database, source)
    before = assert_reported_fixture(scratch_database)
    rows = fiscal_snapshot(scratch_database)
    with scratch_database.connect() as db:
        constraint = db.execute(text("SELECT oid,conindid FROM pg_constraint WHERE conrelid='invoices'::regclass AND conname='invoices_invoice_number_key'")).one()
    assert migrate_legacy_mp(scratch_database) == before
    assert audit_legacy_mp(scratch_database) == before
    assert fiscal_snapshot(scratch_database) == rows
    with scratch_database.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == TARGET
        assert db.execute(text("SELECT oid,conindid FROM pg_constraint WHERE conrelid='invoices'::regclass AND conname='invoices_invoice_number_key'")).one() == constraint
        assert db.scalar(select(func.count()).select_from(MPPaymentIdentity)) == 3828
        assert db.scalar(select(func.count()).select_from(MPPaymentIdentity).where(MPPaymentIdentity.legacy_duplicate)) == 40
        assert db.scalar(select(func.count()).select_from(MPLegacyPaymentSnapshot)) == 3876
        assert db.scalar(select(MPLegacyTransition.source_revision)) == source
        expected = MetaData()
        for table in Base.metadata.sorted_tables:
            table.to_metadata(expected)
        assert compare_metadata(MigrationContext.configure(db), _adoption_metadata(db, expected)) == []
    assert migrate_legacy_mp(scratch_database) == before  # Repetición sin escrituras.


def test_bridge_cli_and_read_only_audit(scratch_database):
    seed_legacy_duplicates(scratch_database)
    before = assert_reported_fixture(scratch_database)
    env = {**os.environ, "DATABASE_URL": scratch_database.url.render_as_string(hide_password=False)}
    for action in ("audit-mp-legacy", "migrate-legacy-mp", "audit-mp-legacy"):
        result = subprocess.run([sys.executable, "-m", "app.manage", action], env=env,
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == before


@pytest.mark.parametrize("failure", ["schema", "money", "integrity", "active-request"])
def test_bridge_rolls_back_ddl_version_and_data_on_failure(scratch_database, monkeypatch, failure):
    seed_legacy_duplicates(scratch_database)
    if failure == "schema":
        with scratch_database.begin() as db:
            db.execute(text("ALTER TABLE payments ADD COLUMN unexpected integer"))
    elif failure == "money":
        with scratch_database.begin() as db:
            db.execute(text("UPDATE payments SET mont=0.333 WHERE id=100"))
    elif failure == "integrity":
        import migrations.mp_legacy_bridge as bridge
        def altered(connection):
            report = integrity_report(connection)
            if connection.scalar(text("SELECT version_num FROM alembic_version")) == TARGET:
                report["sha256"]["payments"] = "SIM-DIFFERENT"
            return report
        monkeypatch.setattr(bridge, "integrity_report", altered)
    else:
        migrate(scratch_database, "0003_billing")
        with scratch_database.begin() as db:
            db.execute(text("""INSERT INTO billing_requests
                (id,idempotency_key,state,total,invoice_date,point,voucher_type,payment_ids,
                 payment_snapshot,fiscal_snapshot,created_at,updated_at)
                VALUES ('SIM-ACTIVE','SIM-ACTIVE','uncertain',1000,'2026-10-01',1,11,'[]','[]','{}',now(),now())"""))
    before = audit_legacy_mp(scratch_database)
    with scratch_database.connect() as db:
        version = db.scalar(text("SELECT version_num FROM alembic_version"))
    with pytest.raises(RuntimeError):
        migrate_legacy_mp(scratch_database)
    assert audit_legacy_mp(scratch_database) == before
    with scratch_database.connect() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == version
        assert "mp_events" not in inspect(db).get_table_names()


def test_duplicates_remain_frozen_and_cannot_be_billed_or_reinserted(scratch_database):
    seed_legacy_duplicates(scratch_database)
    migrate_legacy_mp(scratch_database)
    before = fiscal_snapshot(scratch_database)
    gateway = Mock()
    service = BillingService(engine=scratch_database, gateway_factory=gateway)
    # ID 12: approved, sin marca ni vínculo, pero su grupo está bloqueado.
    with pytest.raises(BillingConflict):
        service.issue([12])
    with Session(scratch_database) as db:
        with pytest.raises(BillingConflict):
            preview_invoice(db, None, [12], session_hash="SIM-SESSION")
        eligible = list(db.scalars(payment_statement(parse_filters("no", default_today=False), eligible=True)))
        assert all(not row.id_payment_mp.startswith("SIM-DUP-") for row in eligible)
        expected = db.scalar(text("""SELECT coalesce(sum(mont),0) FROM payments
            WHERE status='approved' AND registered_arca=false AND mont>0
            AND date_approved::date='2026-10-01' AND id>88"""))
        assert unbilled_mp_total(db, date(2026,10,1)) == expected
    gateway.assert_not_called()
    for statement in ("UPDATE payments SET registered_arca=true WHERE id=12",
                      "UPDATE payments SET raw_json='{}' WHERE id=12",
                      "DELETE FROM payments WHERE id=12",
                      "INSERT INTO payments(id,id_payment_mp,status) VALUES (9999,'SIM-DUP-4','approved')"):
        with pytest.raises(IntegrityError):
            with scratch_database.begin() as db:
                db.execute(text(statement))
    assert fiscal_snapshot(scratch_database) == before


def test_notifications_keep_legacy_rows_and_store_evidence_without_rebilling(scratch_database):
    seed_legacy_duplicates(scratch_database)
    migrate_legacy_mp(scratch_database)
    before = fiscal_snapshot(scratch_database)
    gateway = Mock()
    inbox = MPInbox(engine=scratch_database, gateway_factory=lambda: gateway)
    event = inbox.receive({"id":"SIM-DUP-DELIVERY","data":{"id":"SIM-DUP-4"}})
    inbox.process_one(event)
    gateway.fetch.assert_not_called()
    canonical = resource(identifier="SIM-DUP-4", status="refunded")
    gateway.fetch.return_value = [canonical]
    order = inbox.receive({"id":"SIM-ORDER","type":"merchant_order","data":{"id":"SIM-ORDER"}})
    inbox.process_one(order)
    assert fiscal_snapshot(scratch_database) == before
    with Session(scratch_database) as db:
        assert db.get(MPEvent, event).state == "review"
        assert db.get(MPEvent, order).state == "review"
        assert db.get(MPEvent, order).resource_responses[0]["resources"] == [canonical]
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 0
        assert db.scalar(select(func.count()).select_from(BillingRequest)) == 0


def test_new_notifications_are_concurrent_idempotent_after_bridge(scratch_database):
    seed_legacy_duplicates(scratch_database)
    migrate_legacy_mp(scratch_database)
    gateway = Mock()
    gateway.fetch.return_value = [resource(identifier="SIM-NEW")]
    inbox = MPInbox(engine=scratch_database, gateway_factory=lambda: gateway)
    ids = [inbox.receive({"id":f"SIM-EVENT-{n}","data":{"id":"SIM-NEW"}}) for n in range(4)]
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(inbox.process_one, ids))
    with Session(scratch_database) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 3877
        payment = db.scalar(select(Payment).where(Payment.id_payment_mp == "SIM-NEW"))
        assert db.get(MPPaymentIdentity, "SIM-NEW").payment_id == payment.id
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 1
        assert db.scalar(select(func.count()).select_from(BillingRequest)) == 0
    with ThreadPoolExecutor(max_workers=2) as workers:
        def attempt(_):
            try:
                with scratch_database.begin() as db:
                    db.execute(text("INSERT INTO payments(id_payment_mp,status) VALUES ('SIM-DIRECT','approved')"))
                return True
            except IntegrityError:
                return False
        assert sorted(workers.map(attempt, range(2))) == [False, True]


def test_unique_legacy_updates_keep_initial_snapshot_and_previous_json(scratch_database):
    seed_legacy_duplicates(scratch_database)
    migrate_legacy_mp(scratch_database)
    with Session(scratch_database) as db:
        original = deepcopy(db.get(MPLegacyPaymentSnapshot, 100).snapshot)
    gateway = Mock()
    raw = resource(identifier="SIM-MP-100", amount="100.25", status="refunded")
    gateway.fetch.return_value = [raw]
    inbox = MPInbox(engine=scratch_database, gateway_factory=lambda: gateway)
    event = inbox.receive({"data":{"id":"SIM-MP-100"}})
    inbox.process_one(event)
    with Session(scratch_database) as db:
        assert db.get(Payment, 100).status == "refunded"
        assert db.get(MPLegacyPaymentSnapshot, 100).snapshot == original
        change = db.scalar(select(PaymentChange))
        assert change.previous_data == original
        assert db.get(MPEvent, event).resource_responses[0]["resources"] == [raw]


def test_bridge_with_explicit_invoice_index_preserves_existing_fiscal_evidence(scratch_database):
    seed_legacy_duplicates(scratch_database, invoice_constraint=False)
    migrate(scratch_database, "0003_billing")
    with scratch_database.begin() as db:
        db.execute(text("UPDATE invoices SET fiscal_snapshot=json_build_object('simulation',true), "
                        "raw_afip_response=json_build_object('legacy',true) WHERE id=9"))
        db.execute(text("""INSERT INTO billing_requests
            (id,idempotency_key,state,total,invoice_date,point,voucher_type,payment_ids,
             payment_snapshot,fiscal_snapshot,invoice_id,response,created_at,updated_at)
            VALUES ('SIM-AUTH','SIM-AUTH','authorized',9000.25,'2026-10-01',1,11,'[25]',
                '[]','{}',9,json_build_object('simulation',true),now(),now())"""))
        db.execute(text("INSERT INTO billing_reservations VALUES (25,'SIM-AUTH')"))
    before = audit_legacy_mp(scratch_database)
    assert migrate_legacy_mp(scratch_database) == before
    with scratch_database.connect() as db:
        assert compare_metadata(MigrationContext.configure(db), Base.metadata) == []
        assert db.scalar(select(BillingReservation.request_id)) == "SIM-AUTH"
    with Session(scratch_database) as db:
        metrics = period_metrics(db, date(2026,10,1), date(2026,10,2))
        assert metrics["mp_repeated_count"] == 87
        assert metrics["mp_count"] > metrics["mp_repeated_count"]
        assert metrics["invoice_count"] == 181


def test_audit_runs_in_a_database_read_only_transaction(scratch_database, monkeypatch):
    from sqlalchemy.exc import DBAPIError
    import migrations.mp_legacy_bridge as bridge
    seed_legacy_duplicates(scratch_database)
    def attempted_write(connection):
        connection.execute(text("UPDATE payments SET status='pending' WHERE id=100"))
    monkeypatch.setattr(bridge, "integrity_report", attempted_write)
    with pytest.raises(DBAPIError, match="read-only"):
        audit_legacy_mp(scratch_database)


def test_preexisting_queued_selection_cannot_send_blocked_rows(scratch_database):
    seed_legacy_duplicates(scratch_database)
    migrate_legacy_mp(scratch_database)
    with scratch_database.begin() as db:
        db.execute(text("""INSERT INTO billing_requests
            (id,idempotency_key,state,total,invoice_date,point,voucher_type,payment_ids,
             payment_snapshot,fiscal_snapshot,created_at,updated_at)
            VALUES ('SIM-QUEUED','SIM-QUEUED','queued',4000.25,'2026-10-01',1,11,
                    '[12]','[]','{}',now(),now())"""))
    gateway = Mock()
    assert BillingService(engine=scratch_database, gateway_factory=gateway).process_one_queued()
    gateway.assert_not_called()
    with Session(scratch_database) as db:
        assert db.get(BillingRequest, "SIM-QUEUED").state == "rejected"
        assert db.scalar(text("SELECT count(*) FROM invoices")) == 181


@pytest.mark.parametrize("source", ["0004_mp", "0012_credit_paid_date"])
def test_existing_versioned_installation_uses_ordinary_upgrade(scratch_database, source):
    migrate(scratch_database, source)
    with scratch_database.begin() as db:
        db.execute(text("INSERT INTO payments(id_payment_mp,status,mont,raw_json) VALUES ('SIM-OLD','approved',1000,'{}')"))
    migrate(scratch_database)
    with Session(scratch_database) as db:
        assert db.get(MPPaymentIdentity, "SIM-OLD").payment_id == 1
        assert db.get(MPLegacyPaymentSnapshot, 1).snapshot["id_payment_mp"] == "SIM-OLD"
        assert db.scalar(select(func.count()).select_from(MPLegacyTransition)) == 0
