from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import Mock
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import pytest
from app.core.database import engine
from app.models.billing import BillingRequest, BillingReservation, SimulatedVoucher
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice
from app.services.billing import BillingService, BillingConflict
from app.services.fiscal_gateway import MockFiscalGateway, ArcaFiscalGateway, authorization, voucher_payload, FiscalRejected
from datetime import date


def stored():
    with Session(engine) as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in
                     [Invoice, PaymentInvoice, SimulatedVoucher])


def test_double_submit_and_restart_return_the_same_invoice(client):
    client.post("/dev/examples")
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: BillingService().issue([1, 2]), range(2)))
    assert results[0] == results[1]
    assert results[0].state == "authorized"
    assert BillingService().issue([2, 1, 1]) == results[0]
    assert stored() == (1, 2, 1)


def test_different_batches_are_serialized_with_distinct_numbers(client):
    client.post("/dev/examples")
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda ids: BillingService().issue(ids), [[1], [2, 3]]))
    assert all(r.state == "authorized" for r in results)
    with Session(engine) as db:
        assert list(db.scalars(select(SimulatedVoucher.number).order_by(SimulatedVoucher.number))) == [1, 2]
    assert stored() == (2, 3, 2)


def test_overlapping_batches_cannot_invoice_the_same_payment(client):
    client.post("/dev/examples")
    def run(ids):
        try:
            return BillingService().issue(ids).state
        except BillingConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(run, [[1, 2], [2, 3]]))
    assert sorted(outcomes) == ["authorized", "conflict"]
    assert stored() == (1, 2, 1)


def test_request_and_reservations_are_committed_before_remote_emission(client):
    client.post("/dev/examples")
    class CheckingGateway(MockFiscalGateway):
        def emit(self, payload):
            with Session(engine) as db:
                attempt = db.scalar(select(BillingRequest))
                assert attempt.state == "sending"
                assert attempt.payload == payload
                assert attempt.voucher_number == payload["CbteDesde"]
                assert list(db.scalars(select(BillingReservation.payment_id))) == [1]
            return super().emit(payload)
    assert BillingService(gateway_factory=CheckingGateway).issue([1]).state == "authorized"


def test_lost_response_blocks_new_emissions_and_is_recovered_after_restart(client):
    client.post("/dev/examples")
    class LostResponse(MockFiscalGateway):
        def emit(self, payload):
            super().emit(payload)
            raise TimeoutError("simulated response loss")
    attempt = BillingService(gateway_factory=LostResponse).issue([1])
    assert attempt.state == "uncertain"
    assert stored() == (0, 0, 1)
    assert BillingService().issue([1]).request_id == attempt.request_id
    with pytest.raises(BillingConflict, match="verificar"):
        BillingService().issue([2])
    recovered = BillingService().recover(attempt.request_id)
    assert recovered.state == "authorized"
    assert stored() == (1, 1, 1)


def test_database_failure_after_authorization_rolls_back_all_local_changes(client):
    client.post("/dev/examples")
    class FailedCommit(BillingService):
        def _finalize(self, db, row, response):
            original = db.commit
            def fail():
                raise RuntimeError("simulated DB commit failure after CAE")
            db.commit = fail
            try:
                return super()._finalize(db, row, response)
            finally:
                db.commit = original
    attempt = FailedCommit().issue([1, 2])
    assert attempt.state == "uncertain"
    assert stored() == (0, 0, 1)
    with Session(engine) as db:
        assert not any(db.scalars(select(Payment.registered_arca)))
    assert BillingService().recover(attempt.request_id).state == "authorized"
    assert stored() == (1, 2, 1)


def test_retry_consults_first_and_reuses_exact_number_and_payload(client):
    client.post("/dev/examples")
    class NotDelivered(MockFiscalGateway):
        def emit(self, payload):
            raise TimeoutError("simulated request not delivered")
    attempt = BillingService(gateway_factory=NotDelivered).issue([1])
    with Session(engine) as db:
        payload = deepcopy(db.get(BillingRequest, attempt.request_id).payload)
    gateway = Mock(wraps=MockFiscalGateway(engine))
    service = BillingService(gateway_factory=lambda _: gateway)
    assert service.recover(attempt.request_id, retry=True).state == "authorized"
    gateway.lookup.assert_called_once_with(payload)
    gateway.emit.assert_called_once_with(payload)
    gateway.last_number.assert_not_called()
    assert stored() == (1, 1, 1)


def test_consultation_failure_never_emits_again(client):
    client.post("/dev/examples")
    class Lost(MockFiscalGateway):
        def emit(self, payload):
            raise TimeoutError()
    attempt = BillingService(gateway_factory=Lost).issue([1])
    gateway = Mock()
    gateway.lookup.side_effect = TimeoutError()
    assert BillingService(gateway_factory=lambda _: gateway).recover(attempt.request_id, retry=True).state == "uncertain"
    gateway.emit.assert_not_called()
    assert stored() == (0, 0, 0)


def test_process_interrupt_leaves_sending_state_that_survives_restart(client):
    client.post("/dev/examples")
    class Interrupted(MockFiscalGateway):
        def emit(self, payload):
            super().emit(payload)
            raise SystemExit("simulated process stop")
    with pytest.raises(SystemExit):
        BillingService(gateway_factory=Interrupted).issue([1])
    with Session(engine) as db:
        row = db.scalar(select(BillingRequest))
        assert row.state == "sending"
        attempt_id = row.id
    assert BillingService().recover(attempt_id).state == "authorized"
    assert stored() == (1, 1, 1)


def test_wrong_voucher_response_is_uncertain_instead_of_marking_payment(client):
    client.post("/dev/examples")
    class WrongResponse(MockFiscalGateway):
        def emit(self, payload):
            raw = super().emit(payload)
            raw["FeDetResp"]["FECAEDetResponse"]["CbteDesde"] = 999
            return raw
    assert BillingService(gateway_factory=WrongResponse).issue([1]).state == "uncertain"
    assert stored() == (0, 0, 1)


def test_bounded_transport_uses_explicit_timeout_and_preserves_safety_guard(monkeypatch):
    from app.services.arca import transport
    from app.core.safety import IntegrationSafetyError
    with pytest.raises(IntegrationSafetyError):
        transport.post_sdk(Mock(), "afip/requests", {})
    monkeypatch.setattr(transport, "require_live_integrations", lambda: None)
    fake_post = Mock()
    fake_post.return_value.status_code = 200
    fake_post.return_value.json.return_value = {"simulation": True}
    monkeypatch.setattr(transport.requests, "post", fake_post)
    assert transport.post_sdk(Mock(access_token="SIM"), "afip/requests", {}) == {"simulation": True}
    assert fake_post.call_args.kwargs["timeout"] == (5, 45)
    assert fake_post.call_args.kwargs["allow_redirects"] is False


def test_auth_failure_is_durable_but_does_not_attempt_emission(client):
    client.post("/dev/examples")
    def unavailable(_):
        raise ValueError("simulated missing certificate")
    attempt = BillingService(gateway_factory=unavailable).issue([1])
    assert attempt.state == "prepared"
    with Session(engine) as db:
        assert db.get(BillingRequest, attempt.request_id).payload is None
    assert stored() == (0, 0, 0)
    assert BillingService().recover(attempt.request_id, retry=True).state == "authorized"


def test_explicit_rejection_keeps_response_and_does_not_mark_payment(client):
    client.post("/dev/examples")
    response = {"FeCabResp": {"Resultado": "R"}, "FeDetResp": {"FECAEDetResponse": {"Resultado": "R"}}}
    gateway = Mock(wraps=MockFiscalGateway(engine))
    gateway.emit.return_value = response
    attempt = BillingService(gateway_factory=lambda _: gateway).issue([1])
    assert attempt.state == "rejected"
    with Session(engine) as db:
        assert db.get(BillingRequest, attempt.request_id).response == response
        assert db.get(Payment, 1).registered_arca is False
    assert BillingService().issue([2]).state == "authorized"


def test_pdf_failure_and_repeated_downloads_never_reissue(client, monkeypatch):
    client.post("/dev/examples")
    attempt = BillingService().issue([1])
    with monkeypatch.context() as patch:
        def fail(_):
            raise RuntimeError("simulated PDF error")
        patch.setattr("app.api.invoice.generar_pdf_factura", fail)
        assert client.get(f"/ARCA/invoice/{attempt.invoice_id}/pdf").status_code == 503
    for _ in range(2):
        assert client.get(f"/ARCA/invoice/{attempt.invoice_id}/pdf").status_code == 200
    assert stored() == (1, 1, 1)
    with Session(engine) as db:
        assert db.get(Invoice, attempt.invoice_id).raw_afip_response["simulation"] is True


def test_independent_request_is_idempotent_and_does_not_create_payments():
    service = BillingService()
    first = service.issue(manual_amount="12500.25", idempotency_key="SIM-REQUEST")
    assert first == service.issue(manual_amount="12500.25", idempotency_key="SIM-REQUEST")
    with pytest.raises(BillingConflict):
        service.issue(manual_amount="15000", idempotency_key="SIM-REQUEST")
    assert stored() == (1, 0, 1)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0


@pytest.mark.parametrize("as_list", [False, True])
def test_arca_full_response_contract_without_real_client(as_list):
    raw = {"FeCabResp": {"Resultado": "A"}, "FeDetResp": {"FECAEDetResponse": {
        "Resultado": "A", "CAE": "SIM-AUTH", "CAEFchVto": "20261025", "Observaciones": {"Obs": [{"Code": 1, "Msg": "SIM"}]}}}}
    if as_list:
        raw["FeDetResp"]["FECAEDetResponse"] = [raw["FeDetResp"]["FECAEDetResponse"]]
    original = deepcopy(raw)
    gateway = object.__new__(ArcaFiscalGateway)
    gateway.client = Mock()
    gateway.client.ElectronicBilling.getWSInitialRequest.return_value = {"Auth": {"Token": "SIM"}}
    gateway.client.webService.return_value.executeRequest.return_value = {"FECAESolicitarResult": raw}
    payload = voucher_payload(10000, date(2026, 10, 15), 10, 12)
    assert gateway.emit(payload) == original
    sent = gateway.client.webService.return_value.executeRequest.call_args
    assert sent.args[0] == "FECAESolicitar"
    assert sent.args[1]["FeCAEReq"]["FeDetReq"]["FECAEDetRequest"]["ImpTotal"] == 10000
    assert authorization(raw) == ("SIM-AUTH", date(2026, 10, 25))
    assert raw == original


def test_arca_lookup_validates_identity_amount_and_error_codes():
    payload = voucher_payload(10000, date(2026, 10, 15), 10, 12)
    detail = dict(payload, Resultado="A", CodAutorizacion="SIM-AUTH", FchVto="20261025")
    gateway = object.__new__(ArcaFiscalGateway)
    gateway.client = Mock()
    gateway.client.ElectronicBilling.getWSInitialRequest.return_value = {"Auth": {"Token": "SIM"}}
    ws = gateway.client.webService.return_value
    ws.executeRequest.return_value = {"FECompConsultarResult": {"ResultGet": detail}}
    assert authorization(gateway.lookup(payload))[0] == "SIM-AUTH"
    detail["ImpTotal"] = 20000
    with pytest.raises(ValueError, match="importe"):
        gateway.lookup(payload)
    ws.executeRequest.return_value = {"FECompConsultarResult": {"Errors": {"Err": [{"Code": 602}]}}}
    assert gateway.lookup(payload) is None
    ws.executeRequest.return_value = {"FECompConsultarResult": {"Errors": {"Err": [{"Code": 500}]}}}
    with pytest.raises(ValueError, match="confirmar"):
        gateway.lookup(payload)
