from datetime import timezone
from decimal import Decimal
from dateutil.parser import isoparse
from zoneinfo import ZoneInfo

STATUSES = {"approved", "pending", "authorized", "in_process", "in_mediation", "rejected",
            "cancelled", "refunded", "charged_back", "partially_refunded"}


def provider_date(value):
    timestamp = isoparse(value)
    if timestamp.tzinfo is None:
        raise ValueError("La fecha MP debe tener zona horaria")
    return timestamp.astimezone(timezone.utc)


def normalize_payment(raw):
    if not isinstance(raw, dict) or not raw.get("id"):
        raise ValueError("Pago sin identidad")
    identifier = str(raw["id"])
    if len(identifier) > 50:
        raise ValueError("Identidad de pago demasiado larga")
    status = raw.get("status")
    amount = Decimal(str(raw["transaction_amount"]))
    if status not in STATUSES or not amount.is_finite() or not 0 < amount < Decimal("10000000000000000") or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Estado o importe MP inválido")
    refund = Decimal(str(raw.get("transaction_amount_refunded", 0)))
    if not refund.is_finite() or refund < 0 or refund > amount:
        raise ValueError("Importe de devolución inválido")
    if status == "approved" and refund > 0:
        status = "refunded" if refund == amount else "partially_refunded"
    approved_at = raw.get("date_approved")
    if status == "approved" and approved_at is None:
        raise ValueError("Pago aprobado sin fecha de aprobación")
    return {"id_payment_mp": identifier, "status": status, "status_detail": str(raw.get("status_detail", status))[:150],
        "mont": amount, "type_of_paid": str(raw.get("payment_type_id", "unknown"))[:50],
        "date_approved": provider_date(approved_at).astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).replace(tzinfo=None) if approved_at else None,
        "bill": status == "approved", "provider_updated_at": provider_date(raw["date_last_updated"]), "raw_json": raw}


def process_webhook(raw):
    try:
        return {"ok": True, "datos": normalize_payment(raw)}
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return {"ok": False, "tipo": "validation", "error": "Pago incompleto o inválido"}
