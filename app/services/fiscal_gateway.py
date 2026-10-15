"""Adaptadores fiscales. Ninguna importación construye clientes externos."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.billing import SimulatedVoucher


class FiscalRejected(Exception):
    """Respuesta inequívoca de rechazo, nunca un timeout o error de transporte."""


def voucher_payload(total, invoice_date, point, number):
    return {"CantReg": 1, "PtoVta": point, "CbteTipo": 11, "Concepto": 1,
            "DocTipo": 99, "DocNro": 0, "CbteDesde": number, "CbteHasta": number,
            "CbteFch": int(invoice_date.strftime("%Y%m%d")), "ImpTotal": float(total),
            "ImpTotConc": 0, "ImpNeto": float(total), "ImpOpEx": 0, "ImpIVA": 0,
            "ImpTrib": 0, "MonId": "PES", "MonCotiz": 1, "CondicionIVAReceptorId": 5}


def authorization(response, payload=None):
    detail = response["FeDetResp"]["FECAEDetResponse"]
    if isinstance(detail, list):
        if len(detail) != 1:
            raise ValueError("Respuesta fiscal ambigua")
        detail = detail[0]
    if response["FeCabResp"]["Resultado"] == "R" or detail["Resultado"] == "R":
        raise FiscalRejected("El proveedor rechazó el comprobante")
    if response["FeCabResp"]["Resultado"] != "A" or detail["Resultado"] != "A" or not detail["CAE"]:
        raise ValueError("Autorización no confirmada")
    if payload is not None:
        for field in ["PtoVta", "CbteTipo"]:
            if int(response["FeCabResp"][field]) != payload[field]:
                raise ValueError("La autorización corresponde a otro punto o tipo")
        for field in ["CbteDesde", "CbteHasta"]:
            if int(detail[field]) != payload[field]:
                raise ValueError("La autorización corresponde a otro número")
    return str(detail["CAE"]), datetime.strptime(str(detail["CAEFchVto"]), "%Y%m%d").date()


class MockFiscalGateway:
    def __init__(self, engine):
        self.engine = engine

    def last_number(self, point, voucher_type):
        with Session(self.engine) as db:
            return db.scalar(select(func.max(SimulatedVoucher.number)).where(
                SimulatedVoucher.point == point, SimulatedVoucher.voucher_type == voucher_type)) or 0

    def emit(self, payload):
        issued = date.fromisoformat(f"{str(payload['CbteFch'])[:4]}-{str(payload['CbteFch'])[4:6]}-{str(payload['CbteFch'])[6:]}")
        response = {"simulation": True, "FeCabResp": {"Resultado": "A", "PtoVta": payload["PtoVta"], "CbteTipo": 11},
                    "FeDetResp": {"FECAEDetResponse": {"Resultado": "A", "CAE": "SIMULADO-SIN-VALIDEZ",
                    "CbteDesde": payload["CbteDesde"], "CbteHasta": payload["CbteHasta"],
                    "CAEFchVto": (issued + timedelta(days=10)).strftime("%Y%m%d")}}}
        with Session(self.engine) as db:
            db.add(SimulatedVoucher(point=payload["PtoVta"], voucher_type=11, number=payload["CbteDesde"],
                                    payload=payload, response=response))
            db.commit()
        return response

    def lookup(self, payload):
        with Session(self.engine) as db:
            row = db.scalar(select(SimulatedVoucher).where(SimulatedVoucher.point == payload["PtoVta"],
                SimulatedVoucher.voucher_type == payload["CbteTipo"], SimulatedVoucher.number == payload["CbteDesde"]))
            if row is None:
                return None
            if row.payload != payload:
                raise ValueError("El comprobante existente no coincide con la solicitud")
            return row.response


class ArcaFiscalGateway:
    def __init__(self):
        from app.services.arca.auth import get_afip_client
        self.client = get_afip_client()

    def last_number(self, point, voucher_type):
        data = self.client.ElectronicBilling.getWSInitialRequest("FECompUltimoAutorizado")
        data.update(PtoVta=point, CbteTipo=voucher_type)
        result = self.client.webService("wsfe").executeRequest("FECompUltimoAutorizado", data)["FECompUltimoAutorizadoResult"]
        if result.get("Errors"):
            raise ValueError("No se pudo confirmar el último comprobante")
        return int(result["CbteNro"])

    def emit(self, payload):
        detail = dict(payload)
        for name in ["CantReg", "PtoVta", "CbteTipo"]:
            detail.pop(name)
        data = self.client.ElectronicBilling.getWSInitialRequest("FECAESolicitar")
        data["FeCAEReq"] = {"FeCabReq": {name: payload[name] for name in ["CantReg", "PtoVta", "CbteTipo"]},
                            "FeDetReq": {"FECAEDetRequest": detail}}
        return self.client.webService("wsfe").executeRequest("FECAESolicitar", data)["FECAESolicitarResult"]

    def lookup(self, payload):
        # Usar el WS directamente permite leer errores estructurados: el helper
        # de afip.py convierte todos los códigos en excepciones de texto.
        billing = self.client.ElectronicBilling
        ws = self.client.webService("wsfe")
        request = billing.getWSInitialRequest("FECompConsultar")
        request["FeCompConsReq"] = {"CbteNro": payload["CbteDesde"], "PtoVta": payload["PtoVta"], "CbteTipo": 11}
        result = ws.executeRequest("FECompConsultar", request)["FECompConsultarResult"]
        errors = result.get("Errors", {}).get("Err", [])
        if isinstance(errors, dict):
            errors = [errors]
        if errors:
            # 602: no existe comprobante. Los demás errores NO significan ausencia.
            if all(str(e.get("Code")) == "602" for e in errors):
                return None
            raise ValueError("ARCA no pudo confirmar el comprobante consultado")
        detail = result["ResultGet"]
        for field in ["PtoVta", "CbteTipo", "CbteDesde", "CbteHasta", "CbteFch", "Concepto", "DocTipo", "DocNro", "MonId"]:
            if str(detail[field]) != str(payload[field]):
                raise ValueError("El comprobante consultado no coincide con la solicitud")
        if Decimal(str(detail["ImpTotal"])) != Decimal(str(payload["ImpTotal"])) or Decimal(str(detail["MonCotiz"])) != Decimal(str(payload["MonCotiz"])):
            raise ValueError("El importe consultado no coincide con la solicitud")
        return {"recovered": True, "consultation": result, "FeCabResp": {"Resultado": detail["Resultado"],
                "PtoVta": payload["PtoVta"], "CbteTipo": 11},
                "FeDetResp": {"FECAEDetResponse": {"Resultado": detail["Resultado"],
                    "CbteDesde": payload["CbteDesde"], "CbteHasta": payload["CbteHasta"],
                    "CAE": detail["CodAutorizacion"], "CAEFchVto": detail["FchVto"]}}}


def gateway_for(engine):
    from app.core.config import INTEGRATIONS_MODE
    return MockFiscalGateway(engine) if INTEGRATIONS_MODE == "mock" else ArcaFiscalGateway()
