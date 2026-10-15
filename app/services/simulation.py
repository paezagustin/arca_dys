"""Respuestas locales identificables. No importa SDKs ni abre conexiones."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

SCENARIOS = {"approved", "pending", "refunded", "rejected", "api_error"}


def payment_resource(amount, scenario="approved", payment_id=None):
    if scenario not in SCENARIOS:
        raise ValueError("Escenario desconocido")
    return f"sim:{scenario}:{Decimal(str(amount))}:{payment_id or uuid4().hex}"


def simulated_payment(resource):
    try:
        prefix, scenario, amount, payment_id = resource.split(":", 3)
        value = Decimal(amount)
        if prefix != "sim" or scenario not in SCENARIOS or not value.is_finite() or value <= 0:
            return None
        if scenario == "api_error":
            return None
    except (ValueError, ArithmeticError):
        return None
    return {
        "id": f"SIM-{payment_id}", "status": scenario,
        "status_detail": "accredited" if scenario == "approved" else scenario,
        "transaction_amount": str(value), "payment_type_id": "bank_transfer",
        "date_approved": datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).isoformat(),
        "live_mode": False,
    }


def simulated_invoice(amount, invoice_date: date):
    due_date = invoice_date + timedelta(days=10)
    return {
        "ok": True,
        "datos_factura": {
            "numero_factura": f"SIM-{uuid4().hex[:20]}",
            "cae": "SIMULADO-SIN-VALIDEZ",
            "vencimiento_cae": due_date.isoformat(),
        },
        "raw_afip_response": {
            "simulation": True,
            "FeCabResp": {"Resultado": "A"},
            "FeDetResp": {"FECAEDetResponse": {
                "Resultado": "A", "CAE": "SIMULADO-SIN-VALIDEZ",
                "CAEFchVto": due_date.strftime("%Y%m%d"),
            }},
        },
        "pdf_url": None, "pdf_error": None,
        "error": None, "tipo": None, "retryable": False,
    }


def simulated_pdf(invoice):
    # Documento de prueba sin Chromium. El diseño fiscal tiene su etapa propia.
    lines = ["SIMULACION - SIN VALIDEZ FISCAL", str(invoice.invoice_number),
             f"Fecha: {invoice.invoice_date}", f"Total: ARS {invoice.total_amount:.2f}",
             "Este documento no fue enviado a ARCA."]
    escape = lambda value: value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands = "BT /F1 16 Tf 50 780 Td " + " ".join(
        f"({escape(line)}) Tj 0 -30 Td" for line in lines) + " ET"
    stream = commands.encode("ascii", errors="replace")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"]
    result = bytearray(b"%PDF-1.4\n"); offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(result)
