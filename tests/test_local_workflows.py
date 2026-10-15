from io import BytesIO
import pytest
from pypdf import PdfReader
from sqlalchemy import text
from app.core.database import engine
from app.services.simulation import payment_resource


def counts():
    with engine.connect() as connection:
        return tuple(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                     for table in ["payments", "invoices", "payment_invoice"])


def confirm_and_process(client, response):
    from app.services.billing import BillingService
    preview_id = response.url.path.rsplit("/", 1)[-1]
    queued = client.post(f"/ARCA/previews/{preview_id}/confirm")
    assert queued.status_code == 200 and "Factura en proceso" in queued.text
    assert BillingService().process_one_queued()
    return client.get(queued.url)


def test_startup_health_and_logo(client):
    assert client.get("/health").json() == {"status": "ok", "environment": "test", "integrations": "mock"}
    assert "Modo simulado" in client.get("/dev").text
    assert client.get("/assets/logo-dulce-salado.jpg").status_code == 200


def test_examples_are_repeatable_and_complete_invoice_downloads(client):
    client.post("/dev/examples")
    client.post("/dev/examples")
    assert counts() == (3, 0, 0)
    assert "50.000,00" in client.get("/page/invoice").text
    response = client.post("/ARCA/invoice/selected", data={"payment_ids": ["1", "2"]})
    assert response.status_code == 200
    confirm_and_process(client, response)
    assert counts() == (3, 1, 2)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT total_amount FROM invoices")).scalar_one() == 25000
        assert connection.execute(text("SELECT COUNT(*) FROM payments WHERE registered_arca")).scalar_one() == 2
        raw = connection.execute(text("SELECT raw_afip_response FROM invoices")).scalar_one()
        assert raw["simulation"] is True
        assert raw["FeDetResp"]["FECAEDetResponse"]["CAE"] == "SIMULADO-SIN-VALIDEZ"
    pdf = client.get("/ARCA/invoice/1/pdf")
    assert pdf.headers["content-type"] == "application/pdf"
    content = PdfReader(BytesIO(pdf.content)).pages[0].extract_text()
    assert "SIN VALIDEZ FISCAL" in content
    assert "25.000,00" in content
    # Repetir la misma selección no crea otra factura.
    client.post("/ARCA/invoice/selected", data={"payment_ids": ["1", "2"]})
    assert counts() == (3, 1, 2)


def test_single_checkbox_and_total_preserve_current_contract(client):
    client.post("/dev/examples")
    confirm_and_process(client, client.post("/ARCA/invoice/selected", data={"payment_ids": "1"}))
    confirm_and_process(client, client.post("/ARCA/invoice", data={"visible_payment_ids": ["2", "3"]}))
    assert counts() == (3, 2, 3)


@pytest.mark.parametrize("ids", ["abc", "1.5"])
def test_invalid_form_ids_never_create_an_invoice(client, ids):
    response = client.post("/ARCA/invoice/selected", data={"payment_ids": ids})
    assert response.status_code == 422
    assert counts() == (0, 0, 0)


def test_empty_selection_does_not_emit(client):
    assert client.post("/ARCA/invoice/selected").status_code == 422
    assert counts() == (0, 0, 0)


@pytest.mark.parametrize("scenario", ["approved", "pending", "refunded", "rejected", "api_error"])
def test_webhook_without_remote_api(client, scenario):
    from app.services.mp_inbox import MPInbox
    response = client.post("/mp/webhook", json={"resource": payment_resource("10000", scenario)})
    assert response.json()["status"] == "accepted"
    assert counts() == (0, 0, 0)  # ACK durable antes de consultar al proveedor.
    MPInbox().process_one(response.json()["event_id"])
    assert counts()[0] == (0 if scenario == "api_error" else 1)


def test_payment_page_and_audit_render_with_data(client):
    client.post("/dev/examples")
    assert client.get("/page/invoice?fecha_desde=2026-01-01&fecha_hasta=2030-01-01").status_code == 200
    assert client.get("/page/reports-stadistics").status_code == 200


def test_missing_pdf_is_a_404(client):
    assert client.get("/ARCA/invoice/999/pdf").status_code == 404


def test_error_history_works_without_resolution_fields(client):
    created = client.post("/test/error-log", params={"error_type": "pdf", "message": "SIM-PDF"})
    assert created.status_code == 200
    history = client.get("/test/error-logs").json()
    assert history["count"] == 1
    assert history["errors"][0]["message"] == "SIM-PDF"
    assert "resolved" not in history["errors"][0]


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "0", "1.001"])
def test_simulator_rejects_invalid_amounts(client, amount):
    assert client.post("/dev/payments", data={"amount": amount}).status_code == 422
    assert counts() == (0, 0, 0)
