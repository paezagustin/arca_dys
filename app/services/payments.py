from datetime import datetime, timedelta
from dateutil import parser
from zoneinfo import ZoneInfo
def process_webhook(mp_payment: dict) -> dict:

    """Procesa el pago recibido desde el webhook de MercadoPago.

    Args:
        mp_payment (dict): Diccionario con la información del pago desde MercadoPago.

    Returns:
        dict: Diccionario con los datos procesados del pago.
    """
    
    fecha_pago_utc = parser.isoparse(mp_payment["date_approved"])
    fecha_pago_ba = fecha_pago_utc.astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))
    return {
        "id_payment_mp": mp_payment.get("id"),

        "status": mp_payment.get("status"),

        "status_detail": mp_payment.get("status"),

        "mont": float(mp_payment["transaction_amount"]) if mp_payment.get("transaction_amount") else -999.0,

        "type_of_paid": mp_payment.get("payment_type_id") if mp_payment.get("status") == 'approved' else "N/A",

        "date_approved": fecha_pago_ba if mp_payment.get("status") == 'approved' else datetime(9999,12,31),

        "bill": mp_payment.get("status") == "approved",

        "registered_arca": False,
        "id_arca": '',
        "raw_json": mp_payment
    }


