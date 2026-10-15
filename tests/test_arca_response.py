"""Contrato de afip.py 1.2.0 con cliente falso; nunca construye Afip ni abre red."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from app.core.database import engine
from app.services.arca.billing import AFIPBillingError, generate_invoice


def approved_response(as_list=False):
    detail = {
        "Resultado": "A", "CAE": "SIM-AUTHORIZED-NOT-FISCAL",
        "CAEFchVto": "20261025", "CbteDesde": 1234, "CbteHasta": 1234,
        "Observaciones": {"Obs": [{"Code": 999, "Msg": "Observación ficticia"}]},
    }
    return {
        "FeCabResp": {"Resultado": "A", "CantReg": 1, "CbteTipo": 11},
        "FeDetResp": {"FECAEDetResponse": [detail] if as_list else detail},
    }


def fake_client(response):
    billing = Mock(spec=["getLastVoucher", "createVoucher"])
    billing.getLastVoucher.return_value = 1233
    billing.createVoucher.return_value = response
    return SimpleNamespace(ElectronicBilling=billing)


@pytest.mark.parametrize("as_list", [False, True])
def test_full_sdk_response_is_preserved_without_mutation(as_list):
    raw = approved_response(as_list)
    original = deepcopy(raw)
    client = fake_client(raw)
    result = generate_invoice(client, 10000, date(2026, 10, 15))
    assert result["raw_afip_response"] == original == raw
    assert result["cae"] == "SIM-AUTHORIZED-NOT-FISCAL"
    assert result["vencimiento_cae"] == "2026-10-25"
    assert result["numero_factura"] == 1234
    data = client.ElectronicBilling.createVoucher.call_args.args[0]
    assert data["CbteTipo"] == 11
    assert data["ImpTotal"] == 10000
    assert client.ElectronicBilling.createVoucher.call_args.kwargs == {"return_response": True}
    client.ElectronicBilling.createVoucher.assert_called_once()


@pytest.mark.parametrize("case", ["empty", "no_detail", "multiple", "rejected_header", "rejected_detail", "no_cae", "bad_date"])
def test_missing_or_unauthorized_response_is_not_accepted(case):
    raw = approved_response()
    if case == "empty":
        raw = {}
    elif case == "no_detail":
        raw["FeDetResp"]["FECAEDetResponse"] = []
    elif case == "multiple":
        detail = raw["FeDetResp"]["FECAEDetResponse"]
        raw["FeDetResp"]["FECAEDetResponse"] = [detail, deepcopy(detail)]
    elif case == "rejected_header":
        raw["FeCabResp"]["Resultado"] = "R"
    else:
        field, value = {"rejected_detail": ("Resultado", "R"), "no_cae": ("CAE", ""),
                        "bad_date": ("CAEFchVto", "invalid")}[case]
        raw["FeDetResp"]["FECAEDetResponse"][field] = value
    with pytest.raises(AFIPBillingError, match="sin autorización válida"):
        generate_invoice(fake_client(raw), 10000, date(2026, 10, 15))


def test_response_reaches_database_even_if_pdf_fails(client, monkeypatch):
    from app.core import config
    from app.services.arca import service

    raw = approved_response(as_list=True)
    fiscal_client = fake_client(raw)

    def broken_pdf(*args):
        raise RuntimeError("SIM-PDF-FAILURE")

    client.post("/dev/examples")
    # Solo se recorre la rama del adaptador. El cliente y el PDF son falsos;
    # los bloqueos HTTP/socket y la red Docker interna siguen activos.
    with monkeypatch.context() as patch:
        patch.setattr(config, "INTEGRATIONS_MODE", "production")
        patch.setattr(service, "get_afip_client", lambda: fiscal_client)
        patch.setattr(service, "generate_invoice_pdf", broken_pdf)
        response = client.post("/ARCA/invoice/selected", data={"payment_ids": "1"})
    assert response.status_code == 200
    with engine.connect() as connection:
        assert connection.execute(text("SELECT raw_afip_response FROM invoices")).scalar_one() == raw
        assert connection.execute(text("SELECT registered_arca FROM payments WHERE id=1")).scalar_one() is True
        assert "SIM-PDF-FAILURE" in connection.execute(text("SELECT message FROM error_logs")).scalar_one()
    assert client.get("/ARCA/invoice/1/pdf").status_code == 200
    assert client.get("/ARCA/invoice/1/pdf").status_code == 200
    fiscal_client.ElectronicBilling.createVoucher.assert_called_once()
