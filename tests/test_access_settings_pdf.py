import re
from base64 import b64decode
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import json
from types import SimpleNamespace
from urllib.parse import urlparse, parse_qs
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pypdf import PdfReader
from app.main import app
from app.core import config
from app.core.database import engine
from app.models.billing import utcnow
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.settings import User, WebSession, BillingPreview
from app.services.access import COOKIE, create_user, start_session, ensure_local_admin, authenticate, hash_password, verify_password
from app.services.settings import defaults, save_settings
from app.services.billing import BillingService
from app.services.invoices import render_invoice_pdf, qr_value, split_amount


def test_public_pages_allow_guests_and_operations_require_csrf_without_emitting():
    with TestClient(app) as raw:
        assert raw.get("/health").status_code == 200
        assert raw.get("/page/invoice", follow_redirects=False).status_code == 200
        assert raw.post("/ARCA/invoice/selected", data={"payment_ids": "1"}, follow_redirects=False).status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0


def test_csrf_body_token_works_missing_token_is_rejected_and_logout_revokes_session(client):
    csrf = client.headers.pop("x-csrf-token")
    cookie = client.cookies.get(COOKIE)
    assert client.post("/dev/examples").status_code == 403
    assert client.post("/dev/examples", data={"csrf_token": csrf}).status_code == 200
    assert client.post("/logout", data={"csrf_token": csrf}).status_code == 200
    with TestClient(app) as replay:
        replay.cookies.set(COOKIE, cookie)
        assert replay.get("/settings", follow_redirects=False).status_code == 303


def test_expired_session_is_rejected(client):
    with Session(engine) as db:
        for row in db.scalars(select(WebSession)):
            row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/settings", follow_redirects=False).status_code == 303
    assert client.get("/page/invoice", follow_redirects=False).status_code == 200


def test_operator_cannot_change_configuration(client):
    with Session(engine) as db:
        user = create_user(db, "operadora", "SIM-operadora-password", "operator")
        token, csrf = start_session(db, user)
    with TestClient(app) as operator:
        operator.cookies.set(COOKIE, token)
        operator.headers["x-csrf-token"] = csrf
        assert operator.get("/settings").status_code == 403
        assert operator.post("/settings", data={}).status_code == 403
        assert operator.get("/page/invoice/manual").status_code == 200
        assert operator.post("/logout").status_code == 200
        assert operator.get("/settings", follow_redirects=False).status_code == 303


def test_passwords_are_hashed_and_local_account_is_not_created_in_production(monkeypatch):
    hashed = hash_password("SIM-password-for-test")
    assert "SIM-password-for-test" not in hashed
    assert verify_password("SIM-password-for-test", hashed)
    assert not verify_password("wrong", hashed)
    monkeypatch.setattr(config, "ENV", "production")
    monkeypatch.setattr(config, "INTEGRATIONS_MODE", "production")
    fake = Mock()
    ensure_local_admin(fake)
    fake.scalar.assert_not_called()


def test_login_is_throttled_after_repeated_invalid_attempts(client):
    with Session(engine) as db:
        for _ in range(10):
            assert authenticate(db, "admin", "wrong", "SIM-ADDRESS") is None
        assert authenticate(db, "admin", "pruebas-locales", "SIM-ADDRESS") is None


def test_settings_change_preserves_existing_invoice_snapshot_without_change_history(client):
    first = BillingService().issue(manual_amount="15000.01", idempotency_key="SIM-SNAPSHOT")
    with Session(engine) as db:
        original = deepcopy(db.get(Invoice, first.invoice_id).fiscal_snapshot)
        values = defaults()
        values["name"], values["minimum"] = "Nuevo emisor de prueba", "2000"
        save_settings(db, values, 0, "admin")
        assert db.get(Invoice, first.invoice_id).fiscal_snapshot == original
        with pytest.raises(ValueError, match="otra pantalla"):
            save_settings(db, values, 0, "admin")
        db.rollback()
    with pytest.raises(ValueError, match="entre"):
        BillingService().issue(manual_amount="1500", idempotency_key="SIM-BELOW-NEW-MIN")
    second = BillingService().issue(manual_amount="2000", idempotency_key="SIM-NEW-SETTINGS")
    with Session(engine) as db:
        assert db.get(Invoice, second.invoice_id).fiscal_snapshot["name"] == values["name"]


def test_independent_invoice_requires_review_and_repeated_confirmation_does_not_duplicate(client):
    response = client.post("/ARCA/invoice/manual/preview", data={"amount": "12345.67"})
    assert response.status_code == 200 and "Revisá antes de facturar" in response.text
    with Session(engine) as db:
        preview = db.scalar(select(BillingPreview))
        identifier = preview.id
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
    for _ in range(2):
        response = client.post(f"/ARCA/previews/{identifier}/confirm")
        assert response.status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
    assert BillingService().process_one_queued()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert Decimal(str(db.scalar(select(Invoice.total_amount)))) == Decimal("12345.67")


def test_expired_confirmation_and_changed_settings_do_not_emit(client):
    client.post("/ARCA/invoice/manual/preview", data={"amount": "10000"})
    with Session(engine) as db:
        preview = db.scalar(select(BillingPreview))
        identifier = preview.id
        preview.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.post(f"/ARCA/previews/{identifier}/confirm").status_code == 409
    client.post("/ARCA/invoice/manual/preview", data={"amount": "10000"})
    with Session(engine) as db:
        preview = db.scalar(select(BillingPreview).where(BillingPreview.id != identifier))
        other = preview.id
        save_settings(db, defaults(), 0, "admin")
    assert client.post(f"/ARCA/previews/{other}/confirm").status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0


@pytest.mark.parametrize("amount", ["0", "999.99", "2000000.01", "NaN", "Infinity", "1000.001"])
def test_independent_invoice_rejects_invalid_amount(client, amount):
    assert client.post("/ARCA/invoice/manual/preview", data={"amount": amount}).status_code == 422


def sample_invoice():
    return SimpleNamespace(invoice_number="00010-00000012", total_amount=Decimal("10001.01"),
        invoice_date=date(2026, 10, 15), cae="12345678901234", cae_due_date=date(2026, 10, 25),
        fiscal_snapshot={"name": "Emisor ficticio para prueba", "address": "Domicilio ficticio 123",
            "cuit": "20409378472", "tax_condition": "Monotributista", "gross_income": "Dato ficticio",
            "start_date": "2020-01-01", "point": 10, "number": 12, "voucher_type": 11, "simulation": False})


def test_qr_encodes_persisted_invoice_and_exact_decimal_split():
    invoice = sample_invoice()
    data = json.loads(b64decode(parse_qs(urlparse(qr_value(invoice)).query)["p"][0]))
    assert data == {"ver": 1, "fecha": "2026-10-15", "cuit": 20409378472, "ptoVta": 10,
        "tipoCmp": 11, "nroCmp": 12, "importe": 10001.01, "moneda": "PES", "ctz": 1,
        "tipoDocRec": 99, "nroDocRec": 0, "tipoCodAut": "E", "codAut": 12345678901234}
    first, second = split_amount("10001.01")
    assert (first, second) == (Decimal("5000.51"), Decimal("5000.50"))
    assert first + second == Decimal("10001.01")


def test_printed_pdf_qr_is_decodable_and_issuer_condition_is_consistent():
    import pypdfium2 as pdfium
    import zxingcpp
    invoice = sample_invoice()
    content = render_invoice_pdf(invoice)
    parsed = PdfReader(BytesIO(content))
    assert len(parsed.pages) == 1
    text = parsed.pages[0].extract_text()
    assert "Monotributista" in text and "Responsable inscripto" not in text
    assert "Efectivo" in text and "Cotillón" in text and "Repostería" in text
    document = pdfium.PdfDocument(content)
    image = document[0].render(scale=3).to_pil()
    codes = zxingcpp.read_barcodes(image)
    assert len(codes) == 1 and codes[0].text == qr_value(invoice)
    document.close()


def test_simulation_and_legacy_documents_do_not_invent_fiscal_qr():
    invoice = sample_invoice()
    simulated = render_invoice_pdf(invoice, simulated=True)
    assert "SIN VALIDEZ FISCAL" in PdfReader(BytesIO(simulated)).pages[0].extract_text()
    assert qr_value(invoice, simulated=True).startswith("SIMULACION|")
    invoice.fiscal_snapshot = None
    assert qr_value(invoice) is None
    historic = render_invoice_pdf(invoice)
    assert "DATOS FISCALES INCOMPLETOS" in PdfReader(BytesIO(historic)).pages[0].extract_text()
