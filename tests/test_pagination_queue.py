from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import Mock
from uuid import uuid4
import re
import pytest
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.billing import BillingRequest, SimulatedVoucher, utcnow
from app.models.settings import BillingPreview
from app.services.billing import BillingService
from app.services.fiscal_gateway import MockFiscalGateway
from app.services.listings import business_today


def seed_payments(count, prefix="SIM-PAGE", amount="1000", day=None):
    with Session(engine) as db:
        for index in range(count):
            db.add(Payment(id_payment_mp=f"{prefix}-{index}", status="approved", mont=Decimal(amount),
                date_approved=datetime.combine(day or business_today(), time(12)), registered_arca=False))
        db.commit()


def test_payment_pages_are_stable_disjoint_and_sql_limited(client):
    seed_payments(32)
    statements = []
    def trace(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", trace)
    try:
        first = client.get("/page/invoice")
        second = client.get("/page/invoice?payments_page=2")
    finally:
        event.remove(engine, "before_cursor_execute", trace)
    ids_first = set(re.findall(r'data-payment-id="(\d+)"', first.text))
    ids_second = set(re.findall(r'data-payment-id="(\d+)"', second.text))
    assert len(ids_first) == 25 and len(ids_second) == 7
    assert not ids_first & ids_second and len(ids_first | ids_second) == 32
    assert first.context["count"] == 32 and first.context["total"] == Decimal("32000.00")
    item_queries = [s for s in statements if s.lstrip().startswith("SELECT payments.id,")]
    assert item_queries and all("LIMIT" in s for s in item_queries)
    clamped = client.get("/page/invoice?payments_page=999999999")
    assert clamped.context["payments"].number == 2


def test_facturar_todo_covers_filter_not_visible_ids_and_confirmation_freezes_membership(client):
    seed_payments(32)
    yesterday = business_today() - timedelta(days=1)
    seed_payments(1, "SIM-OTHER-DAY", day=yesterday)
    response = client.post("/ARCA/invoice", data={"visible_payment_ids": "1"})
    assert response.status_code == 200
    preview = response.context["preview"]
    assert len(preview.payment_ids) == 32 and preview.total == Decimal("32000.00")
    seed_payments(1, "SIM-LATE")
    queued = client.post(f"/ARCA/previews/{preview.id}/confirm")
    assert "Factura en proceso" in queued.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
    assert BillingService().process_one_queued()
    with Session(engine) as db:
        assert db.scalar(select(Invoice.total_amount)) == 32000
        assert db.scalar(select(func.count()).select_from(Payment).where(Payment.registered_arca.is_(True))) == 32
        assert db.scalar(select(Payment.registered_arca).where(Payment.id_payment_mp == "SIM-LATE-0")) is False
        assert db.scalar(select(Payment.registered_arca).where(Payment.id_payment_mp == "SIM-OTHER-DAY-0")) is False


def test_selected_payments_must_belong_to_filter_and_stay_eligible(client):
    seed_payments(1)
    seed_payments(1, "SIM-OLD", day=business_today() - timedelta(days=1))
    assert client.post("/ARCA/invoice/selected", data={"payment_ids": ["1", "2"]}).status_code == 409
    response = client.post("/ARCA/invoice/selected", data={"payment_ids": "1"})
    preview = response.context["preview"]
    with Session(engine) as db:
        db.get(Payment, 1).status = "refunded"
        db.commit()
    assert client.post(f"/ARCA/previews/{preview.id}/confirm").status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0


def test_reserved_payments_are_shown_but_cannot_be_selected_for_a_new_request(client):
    seed_payments(2)
    BillingService().issue([1], enqueue=True)
    page = client.get("/page/invoice")
    assert page.context["payments"].total == 2
    assert page.context["eligible_count"] == 1
    assert page.context["eligible_page_ids"] == {2}
    assert "En solicitud" in page.text
    preview = client.post("/ARCA/invoice").context["preview"]
    assert preview.payment_ids == [2]


def test_audit_lists_are_paginated_and_amount_coincidence_is_not_treated_as_duplicate(client):
    seed_payments(31)
    page = client.get("/page/reports-stadistics?amounts_page=2&page_size=10")
    assert page.status_code == 200
    assert page.context["by_id"].total == 0
    assert page.context["by_amount"].total == 31
    assert len(re.findall(r'data-audit-payment-id="\d+"', page.text)) == 10
    assert "no demuestra una duplicación" in page.text
    assert "amounts_page=3" in page.text
    assert client.get("/page/reports-statistics").status_code == 200


def test_all_payment_states_are_visible_separately_from_eligible_billing(client):
    seed_payments(1)
    seed_payments(1, "SIM-REFUND")
    with Session(engine) as db:
        db.get(Payment, 2).status = "refunded"
        db.commit()
    all_payments = client.get("/page/payments")
    assert all_payments.context["payments"].total == 2
    assert "Devuelto" in all_payments.text
    assert client.get("/page/invoice").context["payments"].total == 1


def test_invoice_and_request_lists_have_independent_pages(client):
    with Session(engine) as db:
        for index in range(31):
            invoice = Invoice(invoice_number=f"SIM-PAGE-I-{index}", total_amount=1000, invoice_date=business_today())
            db.add(invoice)
            db.flush()
            db.add(BillingRequest(id=str(uuid4()), idempotency_key=f"SIM-PAGE-R-{index}", state="authorized",
                total=1000, invoice_date=business_today(), point=10, voucher_type=11,
                payment_ids=[], payment_snapshot=[], fiscal_snapshot={"simulation": True}, invoice_id=invoice.id))
        db.commit()
    page = client.get("/page/invoice?invoices_page=2&requests_page=1")
    assert page.context["invoices"].number == 2 and len(page.context["invoices"].items) == 6
    assert page.context["attempts"].number == 1 and len(page.context["attempts"].items) == 25
    assert "invoices_page=2&amp;requests_page=2" in page.text
    history = client.get("/page/billing-requests?page=2")
    assert len(history.context["attempts"].items) == 6


def test_mp_notifications_are_paginated_and_invalid_page_is_clamped(client):
    from app.models.mp_event import MPEvent
    with Session(engine) as db:
        for index in range(55):
            db.add(MPEvent(id=str(uuid4()), dedup_key=f"SIM-EVENT-{index}", topic="payment", resource="SIM",
                payload={"simulation": True}, state="ignored", attempts=1))
        db.commit()
    page = client.get("/settings/mp?page=2")
    assert page.status_code == 200 and len(page.context["events"].items) == 25
    assert page.context["events"].total == 55
    assert client.get("/settings/mp?page=9999").context["events"].number == 3


@pytest.mark.parametrize("query", ["fecha_desde=bad", "fecha_desde=2026-12-01&fecha_hasta=2026-01-01",
    "payments_page=0", "page_size=1000", "facturado=invalid"])
def test_invalid_filters_have_readable_html_and_never_emit(client, query):
    response = client.get("/page/invoice?" + query, headers={"accept": "text/html"})
    assert response.status_code == 422
    assert "No pudimos completar" in response.text
    assert "<traceback" not in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0


def test_queue_does_not_call_provider_during_web_confirmation_and_can_run_after_restart(client):
    seed_payments(1)
    gateway = Mock(wraps=MockFiscalGateway(engine))
    service = BillingService(gateway_factory=lambda _: gateway)
    outcome = service.issue([1], enqueue=True)
    assert outcome.state == "queued"
    gateway.emit.assert_not_called()
    restarted = BillingService(gateway_factory=lambda _: gateway)
    assert restarted.process_one_queued()
    assert restarted.schedule(outcome.request_id, retry=True).state == "authorized"
    gateway.emit.assert_called_once()


def test_two_workers_cannot_emit_a_queued_request_twice(client):
    seed_payments(2)
    service = BillingService()
    service.issue([1], enqueue=True)
    service.issue([2], enqueue=True)
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda _: BillingService().process_one_queued(), range(2)))
    for _ in range(3):
        if not service.process_one_queued():
            break
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 2
        assert db.scalar(select(func.count()).select_from(SimulatedVoucher)) == 2


def test_orphaned_sending_request_is_consulted_after_restart_without_reissuing(client):
    seed_payments(1)
    class Interrupted(MockFiscalGateway):
        def emit(self, payload):
            super().emit(payload)
            raise SystemExit()
    with pytest.raises(SystemExit):
        BillingService(gateway_factory=Interrupted).issue([1])
    assert BillingService().process_one_queued()
    with Session(engine) as db:
        assert db.scalar(select(BillingRequest.state)) == "authorized"
        assert db.scalar(select(func.count()).select_from(SimulatedVoucher)) == 1


def test_active_sending_request_is_not_mistaken_for_interrupted_process(client):
    seed_payments(1)
    ready, release = Event(), Event()
    class Slow(MockFiscalGateway):
        def emit(self, payload):
            ready.set()
            assert release.wait(5)
            return super().emit(payload)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(lambda: BillingService(gateway_factory=Slow).issue([1]))
        assert ready.wait(5)
        try:
            assert BillingService().process_one_queued() is False
        finally:
            release.set()
        assert future.result().state == "authorized"


def test_payment_changed_after_queue_is_not_sent_to_provider(client):
    seed_payments(1)
    service = BillingService()
    outcome = service.issue([1], enqueue=True)
    with Session(engine) as db:
        db.get(Payment, 1).status = "refunded"
        db.commit()
    assert service.process_one_queued()
    with Session(engine) as db:
        assert db.get(BillingRequest, outcome.request_id).state == "rejected"
        assert db.scalar(select(func.count()).select_from(SimulatedVoucher)) == 0


def test_lost_commit_acknowledgement_does_not_overwrite_authorized_state(client):
    seed_payments(1)
    class LostCommitAck(BillingService):
        def _finalize(self, db, row, response):
            original = db.commit
            def committed_but_ack_lost():
                original()
                raise RuntimeError("simulated COMMIT acknowledgement loss")
            db.commit = committed_but_ack_lost
            try:
                return super()._finalize(db, row, response)
            finally:
                db.commit = original
    outcome = LostCommitAck().issue([1])
    assert outcome.state == "authorized"
    gateway = Mock(wraps=MockFiscalGateway(engine))
    assert BillingService(gateway_factory=lambda _: gateway).recover(outcome.request_id).state == "authorized"
    gateway.lookup.assert_not_called()
    gateway.emit.assert_not_called()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(SimulatedVoucher)) == 1


def test_pdf_error_html_survives_database_rollback_and_keeps_invoice(client, monkeypatch):
    seed_payments(1)
    outcome = BillingService().issue([1])
    def broken(_):
        raise RuntimeError("SIM-PDF-ERROR")
    monkeypatch.setattr("app.api.invoice.generar_pdf_factura", broken)
    response = client.get(f"/ARCA/invoice/{outcome.invoice_id}/pdf", headers={"accept": "text/html"})
    assert response.status_code == 503
    assert "Intentá descargar el PDF nuevamente" in response.text
    assert "Traceback" not in response.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
