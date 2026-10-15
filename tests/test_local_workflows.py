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


def test_startup_health_and_logo(client):
    assert client.get("/health").json() == {"status": "ok", "environment": "test", "integrations": "mock"}
    assert "Modo simulado" in client.get("/dev").text
    assert client.get("/assets/logo-dulce-salado.jpg").status_code == 200


def test_examples_are_repeatable_and_complete_invoice_downloads(client):
    client.post("/dev/examples")
    client.post("/dev/examples")
    assert counts() == (3, 0, 0)
    assert "50000" in client.get("/page/invoice").text
    response = client.post("/ARCA/invoice/selected", data={"payment_ids": ["1", "2"]})
    assert response.status_code == 200
    assert counts() == (3, 1, 2)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT total_amount FROM invoices")).scalar_one() == 25000
        assert connection.execute(text("SELECT COUNT(*) FROM payments WHERE registered_arca")).scalar_one() == 2
    pdf = client.get("/ARCA/invoice/1/pdf")
    assert pdf.headers["content-type"] == "application/pdf"
    content = PdfReader(BytesIO(pdf.content)).pages[0].extract_text()
    assert "SIN VALIDEZ FISCAL" in content
    assert "25000" in content
    # Repetir la misma selección no crea otra factura.
    client.post("/ARCA/invoice/selected", data={"payment_ids": ["1", "2"]})
    assert counts() == (3, 1, 2)


def test_single_checkbox_and_total_preserve_current_contract(client):
    client.post("/dev/examples")
    assert client.post("/ARCA/invoice/selected", data={"payment_ids": "1"}).status_code == 200
    assert client.post("/ARCA/invoice", data={"visible_payment_ids": ["2", "3"]}).status_code == 200
    assert counts() == (3, 2, 3)


@pytest.mark.parametrize("ids", ["abc", "1.5"])
def test_invalid_form_ids_never_create_an_invoice(client, ids):
    response = client.post("/ARCA/invoice/selected", data={"payment_ids": ids})
    assert response.status_code == 422
    assert counts() == (0, 0, 0)


def test_empty_selection_does_not_emit(client):
    assert client.post("/ARCA/invoice/selected").status_code == 200
    assert counts() == (0, 0, 0)


@pytest.mark.parametrize("scenario,expected", [("approved", "ok"), ("pending", "ignored"),
    ("refunded", "ignored"), ("rejected", "ignored"), ("api_error", "error")])
def test_webhook_without_remote_api(client, scenario, expected):
    response = client.post("/mp/webhook", json={"resource": payment_resource("10000", scenario)})
    assert response.json()["status"] == expected
    assert counts()[0] == (1 if scenario == "approved" else 0)


def test_payment_page_and_audit_render_with_data(client):
    client.post("/dev/examples")
    assert client.get("/page/invoice?fecha_desde=2026-01-01&fecha_hasta=2030-01-01").status_code == 200
    assert client.get("/page/reports-stadistics").status_code == 200


def test_missing_pdf_is_a_404(client):
    assert client.get("/ARCA/invoice/999/pdf").status_code == 404


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "0", "1.001"])
def test_simulator_rejects_invalid_amounts(client, amount):
    assert client.post("/dev/payments", data={"amount": amount}).status_code == 422
    assert counts() == (0, 0, 0)
