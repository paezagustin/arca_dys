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
    if mp_payment['date_approved'] == None:
		raise ValueError("Date_approved None")
    fecha_pago_utc = parser.isoparse(mp_payment["date_approved"]) if mp_payment["date_approved"] != None else datetime(9999,12,31)
    fecha_pago_ba = fecha_pago_utc.astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))
    
    
    paid_json = {
        "id_payment_mp": mp_payment.get("id") if mp_payment.get("id") != None else 'Without_id',

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
    return paid_json


