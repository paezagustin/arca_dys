from datetime import datetime, timedelta

from dateutil import parser

# En vez de hacer una ventana para pagos aprobados, verificar si ya está en la bd (actualmente en el dataframe)
def pre_process_webhook(payload):
    print("Pre-processing webhook")

    try:
        if payload.get('status') != 'approved':
            print("Status not approved")
            
            json_response = {
                "id_payment_mp": payload.get('id'),
                "status": payload.get('status'),
                "status_detail": 'not approved',
                "mont": '-',
                "type_of_paid": '-',
                "date_approved": None,
                'bill': False,
                'registered_arca': False,
                'id_arca': '',
                "raw_json": payload
            }
            return json_response


        date_approved_str = payload.get('date_approved')


        fecha_pago = parser.isoparse(date_approved_str) + timedelta(hours=1)
        ahora = datetime.now(fecha_pago.tzinfo) + timedelta(hours=1)

        ventana_inicio = ahora - timedelta(minutes=5)
        ventana_fin = ahora + timedelta(minutes=5)

        if not (ventana_inicio <= fecha_pago <= ventana_fin):
            json_response = {
                "id_payment_mp": payload.get('id'),
                "status": "out_of_time_window",
                "status_detail": "The payment date is outside the acceptable time window.",
                "mont": float(payload.get('transaction_amount')),
                "type_of_paid": payload.get('payment_type_id'),
                "date_approved": fecha_pago,
                'bill': False,
                'registered_arca': False,
                'id_arca': '',
                "raw_json": payload
            }
            return json_response

        # Procesamiento OK
        try:

            payment_id = payload.get('id')
            monto = float(payload.get('transaction_amount'))
            tipo_de_pago = payload.get('payment_type_id')
            
            json_response = {
                "id_payment_mp": payment_id,
                "status": "approved",
                "status_detail": "approved",
                "mont": monto,
                "type_of_paid": tipo_de_pago,
                "date_approved": fecha_pago,
                'bill': True,
                'registered_arca': False,
                'id_arca': '',
                "raw_json": payload
            }

            return json_response
        except Exception as e:
            #Ver como manejar este error
            print("Error processing webhook:", e)
            return False

    except Exception as e:
        print("Error in pre_process_webhook:", e)
        #Ver como manejar este error
        return False
    