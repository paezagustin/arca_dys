from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
import hmac
from unittest.mock import Mock
import logging
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core import config
from app.core.database import engine
from app.models.billing import utcnow
from app.models.mp_event import MPEvent, PaymentChange
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.services.mp_inbox import MPInbox, validate_signature, parse_notification
from app.services.mp import MPGateway
from app.services.billing import BillingService, BillingConflict


def resource(status="approved", updated="2026-10-15T12:00:00Z", identifier="SIM-MP-1", amount="10000"):
    return {"id": identifier, "status": status, "status_detail": "accredited" if status == "approved" else status,
        "transaction_amount": amount, "date_approved": "2026-10-15T10:00:00Z" if status in {"approved", "refunded"} else None,
        "date_last_updated": updated, "payment_type_id": "bank_transfer", "collector_id": "SIM-OWNER", "live_mode": True}


def inbox_for(raw):
    gateway = Mock()
    gateway.fetch.return_value = raw if isinstance(raw, list) else [raw]
    return MPInbox(gateway_factory=lambda: gateway), gateway


def test_receive_commits_before_processing_and_duplicate_event_does_not_duplicate_payment():
    inbox, gateway = inbox_for(resource())
    payload = {"id": "SIM-NOTIFY", "type": "payment", "data": {"id": "123"}}
    with ThreadPoolExecutor(max_workers=2) as workers:
        identifiers = list(workers.map(lambda _: inbox.receive(payload), range(2)))
    assert identifiers[0] == identifiers[1]
    gateway.fetch.assert_not_called()
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda _: inbox.process_one(identifiers[0]), range(2)))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.scalar(select(func.count()).select_from(MPEvent)) == 1
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 1
    gateway.fetch.assert_called_once()


def test_duplicate_legacy_deliveries_preserve_history_but_not_duplicate_payments():
    inbox, _ = inbox_for(resource())
    identifiers = [inbox.receive({"resource": "123"}) for _ in range(2)]
    assert identifiers[0] != identifiers[1]
    for identifier in identifiers:
        inbox.process_one(identifier)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 1


def test_concurrent_distinct_events_for_one_payment_are_atomic():
    inbox, _ = inbox_for(resource())
    ids = [inbox.receive({"id": f"SIM-{i}", "data": {"id": "123"}}) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(inbox.process_one, ids))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 1
        assert set(db.scalars(select(MPEvent.state))) <= {"processed", "ignored"}


def test_out_of_order_updates_are_ignored_and_refund_does_not_rewrite_invoice():
    inbox, gateway = inbox_for(resource())
    first = inbox.receive({"resource": "123"})
    inbox.process_one(first)
    outcome = BillingService().issue([1])
    gateway.fetch.return_value = [resource("refunded", "2026-10-15T13:00:00Z")]
    inbox.process_one(inbox.receive({"resource": "123"}))
    gateway.fetch.return_value = [resource("approved", "2026-10-15T11:00:00Z")]
    inbox.process_one(inbox.receive({"resource": "123"}))
    with Session(engine) as db:
        payment = db.get(Payment, 1)
        assert payment.status == "refunded" and payment.registered_arca is True
        assert db.get(Invoice, outcome.invoice_id).total_amount == 10000
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 2


def test_partial_refund_is_not_eligible_for_full_invoice():
    raw = resource()
    raw["transaction_amount_refunded"] = "1000"
    inbox, _ = inbox_for(raw)
    inbox.process_one(inbox.receive({"resource": "123"}))
    with Session(engine) as db:
        assert db.get(Payment, 1).status == "partially_refunded"
    with pytest.raises(BillingConflict):
        BillingService().issue([1])


def test_failures_are_durable_and_can_be_retried_after_restart():
    inbox, gateway = inbox_for(resource())
    gateway.fetch.side_effect = TimeoutError()
    event_id = inbox.receive({"resource": "123"})
    inbox.process_one(event_id)
    with Session(engine) as db:
        row = db.get(MPEvent, event_id)
        assert row.state == "error" and row.attempts == 1
        assert row.next_attempt_at > row.received_at
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
    restarted, _ = inbox_for(resource())
    restarted.retry(event_id)
    restarted.process_one(event_id)
    with Session(engine) as db:
        assert db.get(MPEvent, event_id).state == "processed"
        assert db.get(MPEvent, event_id).attempts == 2
        assert db.scalar(select(func.count()).select_from(Payment)) == 1


def test_batch_validation_failure_rolls_back_all_payment_changes():
    inbox, _ = inbox_for([resource(), resource(identifier="SIM-INVALID", amount="NaN")])
    inbox.process_one(inbox.receive({"resource": "123"}))
    with Session(engine) as db:
        assert db.scalar(select(MPEvent.state)) == "error"
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(PaymentChange)) == 0


def test_conflicting_amount_is_preserved_for_review():
    inbox, gateway = inbox_for(resource())
    inbox.process_one(inbox.receive({"resource": "123"}))
    gateway.fetch.return_value = [resource(amount="20000", updated="2026-10-15T13:00:00Z")]
    identifier = inbox.receive({"resource": "123"})
    inbox.process_one(identifier)
    with Session(engine) as db:
        assert db.get(MPEvent, identifier).state == "error"
        assert db.get(Payment, 1).mont == 10000


@pytest.mark.parametrize("resource_url", ["http://localhost/secrets", "https://evil.example/v1/payments/123",
    "https://api.mercadopago.com/v1/payments/123?other=1", "https://api.mercadopago.com:443/v1/payments/123"])
def test_notification_resource_cannot_choose_an_arbitrary_request_destination(resource_url):
    with pytest.raises(ValueError):
        parse_notification({"resource": resource_url}, {})


def test_signature_manifest_and_body_identity():
    signature = hmac.new(b"SIM-SECRET", b"id:abc;request-id:SIM-REQUEST;ts:1792100000;", "sha256").hexdigest()
    header = "ts=1792100000,v1=" + signature
    assert validate_signature(header, "SIM-REQUEST", "ABC", "SIM-SECRET")
    assert not validate_signature(header, "OTHER", "ABC", "SIM-SECRET")
    assert not validate_signature(header, "SIM-REQUEST", "ABC", "wrong")
    assert not validate_signature("broken", "SIM-REQUEST", "ABC", "SIM-SECRET")
    with pytest.raises(ValueError, match="firmada"):
        parse_notification({"data": {"id": "OTHER"}}, {"data.id": "ABC"})


def test_production_webhook_requires_signature_and_separate_legacy_token(client, monkeypatch):
    monkeypatch.setattr(config, "INTEGRATIONS_MODE", "production")
    monkeypatch.setattr(config, "MP_COLLECTOR_ID", "SIM-OWNER")
    monkeypatch.setattr(config, "MP_WEBHOOK_SECRET", "SIM-SECRET")
    monkeypatch.setattr(config, "MP_LEGACY_WEBHOOK_TOKEN", "SIM-LEGACY-" + "x" * 32)
    body = {"id": "SIM-NOTIFY", "type": "payment", "data": {"id": "123"}}
    assert client.post("/mp/webhook?data.id=123", json=body).status_code == 401
    digest = hmac.new(b"SIM-SECRET", b"id:123;request-id:SIM-R;ts:1792100000;", "sha256").hexdigest()
    headers = {"x-signature": "ts=1792100000,v1=" + digest, "x-request-id": "SIM-R"}
    assert client.post("/mp/webhook?data.id=123", json=body, headers=headers).status_code == 200
    assert client.post("/mp/webhook/legacy/wrong", json={"resource": "123"}).status_code == 401
    assert client.post("/mp/webhook/legacy/" + config.MP_LEGACY_WEBHOOK_TOKEN, json={"resource": "123"}).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0


def test_log_filter_redacts_legacy_webhook_token():
    from app.core.logging import RedactWebhookPath
    record = logging.LogRecord("uvicorn.access", 20, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "POST", "/mp/webhook/legacy/SIM-PRIVATE?topic=payment", "1.1", 200), None)
    RedactWebhookPath().filter(record)
    assert "SIM-PRIVATE" not in record.getMessage()
    assert "REDACTED" in record.getMessage()


def test_point_qr_orders_and_legacy_merchant_orders_use_canonical_payment_identity(monkeypatch):
    monkeypatch.setattr(config, "MP_COLLECTOR_ID", "SIM-OWNER")
    gateway = MPGateway()
    raw = resource(identifier="123")
    resources = {
        "v1/payments/123": raw,
        "merchant_orders/5": {"id": 5, "collector": {"id": "SIM-OWNER"}, "payments": [{"id": 123}]},
        "v1/orders/ORDSIM": {"id": "ORDSIM", "user_id": "SIM-OWNER", "transactions": {"payments": [{"reference_id": "123", "amount": "10000"}]}},
    }
    monkeypatch.setattr(gateway, "_get", lambda path: deepcopy(resources[path]))
    assert gateway.fetch("payment", "123") == [raw]
    assert gateway.fetch("merchant_order", "5") == [raw]
    assert gateway.fetch("order", "ORDSIM") == [raw]
    resources["v1/payments/123"]["collector_id"] = "OTHER"
    with pytest.raises(ValueError, match="otra cuenta"):
        gateway.fetch("payment", "123")


def test_mp_transport_has_timeout_no_redirect_and_only_get(monkeypatch):
    import app.services.mp as module
    monkeypatch.setattr(module, "require_live_integrations", lambda: None)
    monkeypatch.setattr(config, "MP_ACCESS_TOKEN", "SIM-TOKEN")
    monkeypatch.setattr(config, "MP_COLLECTOR_ID", "SIM-OWNER")
    fake_get = Mock()
    fake_get.return_value.status_code = 200
    fake_get.return_value.json.return_value = {"simulation": True}
    monkeypatch.setattr(module.requests, "get", fake_get)
    assert MPGateway()._get("v1/payments/123")["simulation"] is True
    assert fake_get.call_args.kwargs["timeout"] == (5, 10)
    assert fake_get.call_args.kwargs["allow_redirects"] is False
