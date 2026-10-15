from datetime import datetime, timedelta
from dateutil import parser
from zoneinfo import ZoneInfo
import logging


logger = logging.getLogger(__name__)

def process_webhook(mp_payment: dict) -> dict:

    """Procesa el pago recibido desde el webhook de MercadoPago.

    Args:
        mp_payment (dict): Diccionario con la información del pago desde MercadoPago.

    Returns:
        {
            "ok": True/False,
            "datos": {...} si ok=True,
            "error": "mensaje" si ok=False,
            "tipo": "validation|business_rule|system"
        }
    """
    if not mp_payment:
        logger.warning("No payment data to process")
        return {
            "ok": False,
            "error": "Data empty",
            "tipo": "validation"
        }
    status = mp_payment.get("status")
    if status != "approved":
        return {
            "ok": False,
            "error": f"Payment not approved: {status}",
            "tipo": "business_rule"
        }
    try:
        fecha_pago_utc = parser.isoparse(mp_payment["date_approved"]) if mp_payment["date_approved"] != None else datetime(9999,12,31)
        fecha_pago_ba = fecha_pago_utc.astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))
    except Exception as e:
        logger.error(f"Error parsing date_approved: {e}")
        fecha_pago_ba = datetime(9999,12,31)
        return {
            "ok": False,
            "error": f"Error parsing date_approved: {e}",
            "tipo": "validation"
        }   
    
    paid_json = {
        "id_payment_mp": mp_payment.get("id") if mp_payment.get("id") != None else 'Without_id',

        "status": mp_payment.get("status"),

        "status_detail": mp_payment.get("status"),

        "mont": float(mp_payment["transaction_amount"]) if mp_payment.get("transaction_amount") else -999.0,

        "type_of_paid": mp_payment.get("payment_type_id") if mp_payment.get("status") == 'approved' else "N/A",

        "date_approved": fecha_pago_ba if mp_payment.get("status") == 'approved' else datetime(9999,12,31),

        "bill": mp_payment.get("status") == "approved",

        "registered_arca": False,
        "raw_json": mp_payment
    }
    logger.info('Payment processed successfully')
    return {
        "ok": True,
        "datos": paid_json
    }

